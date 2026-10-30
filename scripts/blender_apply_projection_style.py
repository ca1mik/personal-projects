from __future__ import annotations

import argparse
import sys
from math import radians
from pathlib import Path

import bpy
from mathutils import Vector


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description="Apply a projection-driven stylized material to a Blender character mesh.")
    parser.add_argument("--input-blend", help="Source .blend file to open.")
    parser.add_argument("--input-obj", help="Fallback .obj file to import if no blend is provided.")
    parser.add_argument("--output-blend", required=True, help="Path to the styled output .blend.")
    parser.add_argument("--output-glb", required=True, help="Path to the styled output .glb.")
    parser.add_argument("--render-dir", required=True, help="Directory for preview renders.")
    parser.add_argument("--color-front", required=True)
    parser.add_argument("--color-back", required=True)
    parser.add_argument("--color-left", required=True)
    parser.add_argument("--color-right", required=True)
    parser.add_argument("--id-front", required=True)
    parser.add_argument("--id-back", required=True)
    parser.add_argument("--id-left", required=True)
    parser.add_argument("--id-right", required=True)
    parser.add_argument("--look-name", default="Reference Doll")
    return parser.parse_args(argv)


def clear_factory_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablock_collection in (
        bpy.data.meshes,
        bpy.data.materials,
        bpy.data.images,
        bpy.data.lights,
        bpy.data.cameras,
    ):
        for datablock in list(datablock_collection):
            if datablock.users == 0:
                datablock_collection.remove(datablock)


def load_scene(args: argparse.Namespace) -> bpy.types.Object:
    if args.input_blend and Path(args.input_blend).exists():
        bpy.ops.wm.open_mainfile(filepath=args.input_blend)
    else:
        clear_factory_scene()
        if not args.input_obj:
            raise RuntimeError("Either --input-blend or --input-obj is required.")
        bpy.ops.wm.obj_import(filepath=args.input_obj)

    meshes = [obj for obj in bpy.data.objects if obj.type == "MESH"]
    if not meshes:
        raise RuntimeError("No mesh objects were found in the scene.")

    character = max(meshes, key=lambda obj: len(obj.data.vertices))
    bpy.context.view_layer.objects.active = character
    for polygon in character.data.polygons:
        polygon.use_smooth = True
    character.rotation_euler = (0.0, 0.0, 0.0)
    character.scale = (1.0, 1.0, 1.0)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    return character


def world_bounds(obj: bpy.types.Object) -> tuple[Vector, Vector]:
    corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    min_corner = Vector(
        (
            min(corner.x for corner in corners),
            min(corner.y for corner in corners),
            min(corner.z for corner in corners),
        )
    )
    max_corner = Vector(
        (
            max(corner.x for corner in corners),
            max(corner.y for corner in corners),
            max(corner.z for corner in corners),
        )
    )
    return min_corner, max_corner


def _new_node(nodes: bpy.types.Nodes, node_type: str, location: tuple[float, float], label: str | None = None):
    node = nodes.new(node_type)
    node.location = location
    if label:
        node.label = label
        node.name = label
    return node


def _link(links: bpy.types.NodeLinks, source, target) -> None:
    links.new(source, target)


def _map_range_node(
    nodes: bpy.types.Nodes,
    links: bpy.types.NodeLinks,
    input_socket,
    *,
    source_min: float,
    source_max: float,
    target_min: float,
    target_max: float,
    location: tuple[float, float],
    label: str,
) -> bpy.types.ShaderNodeMapRange:
    node = _new_node(nodes, "ShaderNodeMapRange", location, label)
    node.clamp = True
    node.inputs[1].default_value = source_min
    node.inputs[2].default_value = source_max
    node.inputs[3].default_value = target_min
    node.inputs[4].default_value = target_max
    _link(links, input_socket, node.inputs[0])
    return node


def _invert_value(nodes: bpy.types.Nodes, links: bpy.types.NodeLinks, input_socket, location: tuple[float, float], label: str):
    node = _new_node(nodes, "ShaderNodeMath", location, label)
    node.operation = "SUBTRACT"
    node.inputs[0].default_value = 1.0
    _link(links, input_socket, node.inputs[1])
    return node


def _positive_weight(
    nodes: bpy.types.Nodes,
    links: bpy.types.NodeLinks,
    input_socket,
    *,
    invert: bool,
    power: float,
    location: tuple[float, float],
    label: str,
):
    if invert:
        multiply = _new_node(nodes, "ShaderNodeMath", (location[0] - 180, location[1]), f"{label} Negate")
        multiply.operation = "MULTIPLY"
        multiply.inputs[1].default_value = -1.0
        _link(links, input_socket, multiply.inputs[0])
        source_socket = multiply.outputs[0]
    else:
        source_socket = input_socket

    maximum = _new_node(nodes, "ShaderNodeMath", location, f"{label} Clamp")
    maximum.operation = "MAXIMUM"
    maximum.inputs[1].default_value = 0.0
    _link(links, source_socket, maximum.inputs[0])

    exponent = _new_node(nodes, "ShaderNodeMath", (location[0] + 180, location[1]), f"{label} Power")
    exponent.operation = "POWER"
    exponent.inputs[1].default_value = power
    _link(links, maximum.outputs[0], exponent.inputs[0])
    return exponent


def _combine_uv(nodes: bpy.types.Nodes, links: bpy.types.NodeLinks, u_socket, v_socket, location: tuple[float, float], label: str):
    node = _new_node(nodes, "ShaderNodeCombineXYZ", location, label)
    _link(links, u_socket, node.inputs["X"])
    _link(links, v_socket, node.inputs["Y"])
    node.inputs["Z"].default_value = 0.0
    return node


def _image_node(
    nodes: bpy.types.Nodes,
    image_path: Path,
    vector_socket,
    *,
    location: tuple[float, float],
    label: str,
    non_color: bool = False,
) -> bpy.types.ShaderNodeTexImage:
    node = _new_node(nodes, "ShaderNodeTexImage", location, label)
    node.image = bpy.data.images.load(str(image_path), check_existing=True)
    node.extension = "EXTEND"
    node.interpolation = "Linear"
    if non_color:
        node.image.colorspace_settings.name = "Non-Color"
    _link(nodes.id_data.links, vector_socket, node.inputs["Vector"])
    return node


def _scaled_vector(nodes: bpy.types.Nodes, links: bpy.types.NodeLinks, vector_socket, scale_socket, location: tuple[float, float], label: str):
    node = _new_node(nodes, "ShaderNodeVectorMath", location, label)
    node.operation = "SCALE"
    _link(links, vector_socket, node.inputs[0])
    _link(links, scale_socket, node.inputs[3])
    return node


def _add_vector(nodes: bpy.types.Nodes, links: bpy.types.NodeLinks, a_socket, b_socket, location: tuple[float, float], label: str):
    node = _new_node(nodes, "ShaderNodeVectorMath", location, label)
    node.operation = "ADD"
    _link(links, a_socket, node.inputs[0])
    _link(links, b_socket, node.inputs[1])
    return node


def _add_scalar(nodes: bpy.types.Nodes, links: bpy.types.NodeLinks, a_socket, b_socket, location: tuple[float, float], label: str):
    node = _new_node(nodes, "ShaderNodeMath", location, label)
    node.operation = "ADD"
    _link(links, a_socket, node.inputs[0])
    _link(links, b_socket, node.inputs[1])
    return node


def _multiply_scalar(nodes: bpy.types.Nodes, links: bpy.types.NodeLinks, a_socket, b_socket, location: tuple[float, float], label: str):
    node = _new_node(nodes, "ShaderNodeMath", location, label)
    node.operation = "MULTIPLY"
    _link(links, a_socket, node.inputs[0])
    _link(links, b_socket, node.inputs[1])
    return node


def _multiply_scalar_value(nodes: bpy.types.Nodes, links: bpy.types.NodeLinks, a_socket, value: float, location: tuple[float, float], label: str):
    node = _new_node(nodes, "ShaderNodeMath", location, label)
    node.operation = "MULTIPLY"
    _link(links, a_socket, node.inputs[0])
    node.inputs[1].default_value = value
    return node


def _divide_vector(nodes: bpy.types.Nodes, links: bpy.types.NodeLinks, vector_socket, scalar_socket, location: tuple[float, float], label: str):
    node = _new_node(nodes, "ShaderNodeVectorMath", location, label)
    node.operation = "DIVIDE"
    _link(links, vector_socket, node.inputs[0])
    combine = _new_node(nodes, "ShaderNodeCombineXYZ", (location[0] - 180, location[1] - 120), f"{label} ScalarVector")
    _link(links, scalar_socket, combine.inputs["X"])
    _link(links, scalar_socket, combine.inputs["Y"])
    _link(links, scalar_socket, combine.inputs["Z"])
    _link(links, combine.outputs[0], node.inputs[1])
    return node


def create_projection_material(obj: bpy.types.Object, args: argparse.Namespace) -> bpy.types.Material:
    material = bpy.data.materials.new(name=f"{args.look_name} Material")
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    for node in list(nodes):
        nodes.remove(node)

    min_corner, max_corner = world_bounds(obj)
    span = max_corner - min_corner
    min_x, min_y, min_z = min_corner
    max_x, max_y, max_z = max_corner
    span_x = max(max_x - min_x, 1e-5)
    span_y = max(max_y - min_y, 1e-5)
    span_z = max(max_z - min_z, 1e-5)

    texcoord = _new_node(nodes, "ShaderNodeTexCoord", (-2200, 400), "TexCoord")
    geometry = _new_node(nodes, "ShaderNodeNewGeometry", (-2200, -420), "Geometry")
    object_xyz = _new_node(nodes, "ShaderNodeSeparateXYZ", (-1980, 420), "Object XYZ")
    normal_xyz = _new_node(nodes, "ShaderNodeSeparateXYZ", (-1980, -420), "Normal XYZ")
    _link(links, texcoord.outputs["Object"], object_xyz.inputs[0])
    _link(links, geometry.outputs["Normal"], normal_xyz.inputs[0])

    x_norm = _map_range_node(
        nodes,
        links,
        object_xyz.outputs["X"],
        source_min=min_x,
        source_max=max_x,
        target_min=0.0,
        target_max=1.0,
        location=(-1760, 560),
        label="X Norm",
    )
    y_norm = _map_range_node(
        nodes,
        links,
        object_xyz.outputs["Y"],
        source_min=min_y,
        source_max=max_y,
        target_min=0.0,
        target_max=1.0,
        location=(-1760, 360),
        label="Y Norm",
    )
    z_norm = _map_range_node(
        nodes,
        links,
        object_xyz.outputs["Z"],
        source_min=min_z,
        source_max=max_z,
        target_min=0.0,
        target_max=1.0,
        location=(-1760, 160),
        label="Z Norm",
    )

    x_inv = _invert_value(nodes, links, x_norm.outputs[0], (-1540, 560), "X Inv")
    y_inv = _invert_value(nodes, links, y_norm.outputs[0], (-1540, 360), "Y Inv")

    front_uv = _combine_uv(nodes, links, x_norm.outputs[0], z_norm.outputs[0], (-1320, 560), "Front UV")
    back_uv = _combine_uv(nodes, links, x_inv.outputs[0], z_norm.outputs[0], (-1320, 380), "Back UV")
    left_uv = _combine_uv(nodes, links, y_norm.outputs[0], z_norm.outputs[0], (-1320, 200), "Left UV")
    right_uv = _combine_uv(nodes, links, y_inv.outputs[0], z_norm.outputs[0], (-1320, 20), "Right UV")

    front_weight = _positive_weight(
        nodes,
        links,
        normal_xyz.outputs["Y"],
        invert=True,
        power=4.0,
        location=(-1760, -320),
        label="Front Weight",
    )
    back_weight = _positive_weight(
        nodes,
        links,
        normal_xyz.outputs["Y"],
        invert=False,
        power=4.0,
        location=(-1760, -520),
        label="Back Weight",
    )
    left_weight = _positive_weight(
        nodes,
        links,
        normal_xyz.outputs["X"],
        invert=False,
        power=4.0,
        location=(-1760, -720),
        label="Left Weight",
    )
    right_weight = _positive_weight(
        nodes,
        links,
        normal_xyz.outputs["X"],
        invert=True,
        power=4.0,
        location=(-1760, -920),
        label="Right Weight",
    )

    color_front = _image_node(nodes, Path(args.color_front), front_uv.outputs[0], location=(-1040, 680), label="Front Color")
    color_back = _image_node(nodes, Path(args.color_back), back_uv.outputs[0], location=(-1040, 440), label="Back Color")
    color_left = _image_node(nodes, Path(args.color_left), left_uv.outputs[0], location=(-1040, 200), label="Left Color")
    color_right = _image_node(nodes, Path(args.color_right), right_uv.outputs[0], location=(-1040, -40), label="Right Color")

    id_front = _image_node(nodes, Path(args.id_front), front_uv.outputs[0], location=(-1040, -360), label="Front ID", non_color=True)
    id_back = _image_node(nodes, Path(args.id_back), back_uv.outputs[0], location=(-1040, -600), label="Back ID", non_color=True)
    id_left = _image_node(nodes, Path(args.id_left), left_uv.outputs[0], location=(-1040, -840), label="Left ID", non_color=True)
    id_right = _image_node(nodes, Path(args.id_right), right_uv.outputs[0], location=(-1040, -1080), label="Right ID", non_color=True)

    scaled_front = _scaled_vector(nodes, links, color_front.outputs["Color"], front_weight.outputs[0], (-780, 680), "Front Color Weighted")
    scaled_back = _scaled_vector(nodes, links, color_back.outputs["Color"], back_weight.outputs[0], (-780, 440), "Back Color Weighted")
    scaled_left = _scaled_vector(nodes, links, color_left.outputs["Color"], left_weight.outputs[0], (-780, 200), "Left Color Weighted")
    scaled_right = _scaled_vector(nodes, links, color_right.outputs["Color"], right_weight.outputs[0], (-780, -40), "Right Color Weighted")

    id_scaled_front = _scaled_vector(nodes, links, id_front.outputs["Color"], front_weight.outputs[0], (-780, -360), "Front ID Weighted")
    id_scaled_back = _scaled_vector(nodes, links, id_back.outputs["Color"], back_weight.outputs[0], (-780, -600), "Back ID Weighted")
    id_scaled_left = _scaled_vector(nodes, links, id_left.outputs["Color"], left_weight.outputs[0], (-780, -840), "Left ID Weighted")
    id_scaled_right = _scaled_vector(nodes, links, id_right.outputs["Color"], right_weight.outputs[0], (-780, -1080), "Right ID Weighted")

    color_sum_1 = _add_vector(nodes, links, scaled_front.outputs["Vector"], scaled_back.outputs["Vector"], (-520, 580), "Color Sum 1")
    color_sum_2 = _add_vector(nodes, links, scaled_left.outputs["Vector"], scaled_right.outputs["Vector"], (-520, 120), "Color Sum 2")
    color_total = _add_vector(nodes, links, color_sum_1.outputs["Vector"], color_sum_2.outputs["Vector"], (-280, 380), "Color Total")

    id_sum_1 = _add_vector(nodes, links, id_scaled_front.outputs["Vector"], id_scaled_back.outputs["Vector"], (-520, -480), "ID Sum 1")
    id_sum_2 = _add_vector(nodes, links, id_scaled_left.outputs["Vector"], id_scaled_right.outputs["Vector"], (-520, -960), "ID Sum 2")
    id_total = _add_vector(nodes, links, id_sum_1.outputs["Vector"], id_sum_2.outputs["Vector"], (-280, -720), "ID Total")

    weight_sum_1 = _add_scalar(nodes, links, front_weight.outputs[0], back_weight.outputs[0], (-760, -1280), "Weight Sum 1")
    weight_sum_2 = _add_scalar(nodes, links, left_weight.outputs[0], right_weight.outputs[0], (-520, -1280), "Weight Sum 2")
    weight_sum = _add_scalar(nodes, links, weight_sum_1.outputs[0], weight_sum_2.outputs[0], (-280, -1280), "Weight Sum")
    epsilon = _new_node(nodes, "ShaderNodeMath", (-40, -1280), "Weight Epsilon")
    epsilon.operation = "ADD"
    epsilon.inputs[1].default_value = 0.0001
    _link(links, weight_sum.outputs[0], epsilon.inputs[0])

    blended_color = _divide_vector(nodes, links, color_total.outputs["Vector"], epsilon.outputs[0], (-20, 380), "Blended Color")
    blended_id = _divide_vector(nodes, links, id_total.outputs["Vector"], epsilon.outputs[0], (-20, -720), "Blended ID")

    id_separate = _new_node(nodes, "ShaderNodeSeparateColor", (220, -700), "ID Separate")
    _link(links, blended_id.outputs["Vector"], id_separate.inputs["Color"])

    skin_mask = id_separate.outputs["Red"]
    hair_mask = id_separate.outputs["Green"]
    clothes_mask = id_separate.outputs["Blue"]

    rough_skin = _multiply_scalar_value(nodes, links, skin_mask, 0.42, (460, -460), "Skin Roughness")
    rough_hair = _multiply_scalar_value(nodes, links, hair_mask, 0.26, (460, -640), "Hair Roughness")
    rough_clothes = _multiply_scalar_value(nodes, links, clothes_mask, 0.68, (460, -820), "Clothes Roughness")
    rough_sum_1 = _add_scalar(nodes, links, rough_skin.outputs[0], rough_hair.outputs[0], (700, -540), "Rough Sum 1")
    roughness = _add_scalar(nodes, links, rough_sum_1.outputs[0], rough_clothes.outputs[0], (940, -640), "Roughness")

    subsurface = _multiply_scalar_value(nodes, links, skin_mask, 0.08, (460, -1020), "Skin SSS")
    specular_skin = _multiply_scalar_value(nodes, links, skin_mask, 0.45, (460, -1180), "Skin Spec")
    specular_hair = _multiply_scalar_value(nodes, links, hair_mask, 0.65, (460, -1340), "Hair Spec")
    specular_clothes = _multiply_scalar_value(nodes, links, clothes_mask, 0.3, (460, -1500), "Clothes Spec")
    spec_sum_1 = _add_scalar(nodes, links, specular_skin.outputs[0], specular_hair.outputs[0], (700, -1260), "Spec Sum 1")
    specular = _add_scalar(nodes, links, spec_sum_1.outputs[0], specular_clothes.outputs[0], (940, -1380), "Specular")

    principled = _new_node(nodes, "ShaderNodeBsdfPrincipled", (760, 240), "Principled")
    principled.inputs["Base Color"].default_value = (0.94, 0.82, 0.76, 1.0)
    principled.inputs["Roughness"].default_value = 0.45
    principled.inputs["Subsurface Weight"].default_value = 0.04
    principled.inputs["Subsurface Radius"].default_value = (1.0, 0.62, 0.45)
    principled.inputs["Specular IOR Level"].default_value = 0.5
    principled.inputs["Sheen Weight"].default_value = 0.1
    principled.inputs["Coat Weight"].default_value = 0.02
    _link(links, blended_color.outputs["Vector"], principled.inputs["Base Color"])
    _link(links, roughness.outputs[0], principled.inputs["Roughness"])
    _link(links, subsurface.outputs[0], principled.inputs["Subsurface Weight"])
    _link(links, specular.outputs[0], principled.inputs["Specular IOR Level"])

    output = _new_node(nodes, "ShaderNodeOutputMaterial", (1020, 240), "Output")
    _link(links, principled.outputs["BSDF"], output.inputs["Surface"])

    obj.data.materials.clear()
    obj.data.materials.append(material)
    return material


def setup_studio_scene(obj: bpy.types.Object) -> None:
    min_corner, max_corner = world_bounds(obj)
    center = (min_corner + max_corner) * 0.5
    dimensions = max_corner - min_corner
    distance = max(dimensions.x, dimensions.y, dimensions.z) * 2.2

    available_engines = {item.identifier for item in bpy.context.scene.render.bl_rna.properties["engine"].enum_items}
    bpy.context.scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in available_engines else "BLENDER_EEVEE"
    bpy.context.scene.render.resolution_x = 1080
    bpy.context.scene.render.resolution_y = 1440
    bpy.context.scene.render.film_transparent = False
    bpy.context.scene.eevee.taa_render_samples = 64
    bpy.context.scene.world.color = (0.85, 0.85, 0.87)

    for obj_ in [item for item in bpy.data.objects if item.type == "LIGHT"]:
        bpy.data.objects.remove(obj_, do_unlink=True)

    lights = [
        ("Key", (distance * 0.7, -distance * 0.9, center.z + dimensions.z * 0.65), 2200),
        ("Fill", (-distance * 0.9, -distance * 0.5, center.z + dimensions.z * 0.35), 950),
        ("Rim", (0.0, distance * 1.2, center.z + dimensions.z * 0.8), 1600),
    ]
    for name, location, energy in lights:
        light_data = bpy.data.lights.new(name, "AREA")
        light_data.energy = energy
        light_data.shape = "RECTANGLE"
        light_data.size = max(dimensions.x, dimensions.z) * 1.1
        light = bpy.data.objects.new(name, light_data)
        light.location = location
        bpy.context.scene.collection.objects.link(light)

    camera = bpy.data.objects.get("StyleCamera")
    if camera is None:
        camera_data = bpy.data.cameras.new("StyleCamera")
        camera = bpy.data.objects.new("StyleCamera", camera_data)
        bpy.context.scene.collection.objects.link(camera)
    bpy.context.scene.camera = camera
    camera.data.lens = 65
    camera.data.sensor_width = 36


def render_previews(obj: bpy.types.Object, render_dir: Path) -> None:
    render_dir.mkdir(parents=True, exist_ok=True)
    min_corner, max_corner = world_bounds(obj)
    center = (min_corner + max_corner) * 0.5
    dimensions = max_corner - min_corner
    radius = max(dimensions.x, dimensions.y, dimensions.z) * 1.85
    camera = bpy.context.scene.camera

    views = {
        "front": (Vector((center.x, center.y - radius, center.z + dimensions.z * 0.02)), (radians(88), 0.0, 0.0)),
        "left": (Vector((center.x + radius, center.y, center.z + dimensions.z * 0.02)), (radians(88), 0.0, radians(90))),
        "back": (Vector((center.x, center.y + radius, center.z + dimensions.z * 0.02)), (radians(88), 0.0, radians(180))),
        "iso": (Vector((center.x + radius * 0.8, center.y - radius * 0.9, center.z + dimensions.z * 0.12)), (radians(80), 0.0, radians(42))),
    }

    for name, (location, rotation) in views.items():
        camera.location = location
        camera.rotation_euler = rotation
        bpy.context.scene.render.filepath = str(render_dir / f"{name}.png")
        bpy.ops.render.render(write_still=True)


def save_outputs(args: argparse.Namespace) -> None:
    output_blend = Path(args.output_blend)
    output_glb = Path(args.output_glb)
    output_blend.parent.mkdir(parents=True, exist_ok=True)
    output_glb.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(output_blend))
    bpy.ops.export_scene.gltf(
        filepath=str(output_glb),
        export_format="GLB",
        use_selection=False,
        export_apply=False,
        export_animations=False,
        export_normals=True,
        export_yup=True,
        export_texcoords=True,
        export_materials="EXPORT",
    )


def main() -> None:
    args = parse_args()
    character = load_scene(args)
    create_projection_material(character, args)
    setup_studio_scene(character)
    render_previews(character, Path(args.render_dir))
    save_outputs(args)
    print(f"Styled outputs saved to {args.output_blend} and {args.output_glb}")


if __name__ == "__main__":
    main()
