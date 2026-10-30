from __future__ import annotations

import argparse
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description="Create a simple humanoid autorig for an imported mesh.")
    parser.add_argument("--input", required=True, help="Path to the source GLB or OBJ mesh.")
    parser.add_argument("--output-glb", required=True, help="Path to the exported rigged GLB.")
    parser.add_argument("--output-fbx", required=True, help="Path to the exported rigged FBX.")
    parser.add_argument("--rig-name", default="EnyaRig", help="Armature object name.")
    return parser.parse_args(argv)


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in (bpy.data.meshes, bpy.data.armatures, bpy.data.materials, bpy.data.images):
        for item in list(block):
            if item.users == 0:
                block.remove(item)


def import_mesh(input_path: Path) -> list[bpy.types.Object]:
    suffix = input_path.suffix.lower()
    if suffix in {".glb", ".gltf"}:
        bpy.ops.import_scene.gltf(filepath=str(input_path))
    elif suffix == ".obj":
        bpy.ops.wm.obj_import(filepath=str(input_path))
    else:
        raise RuntimeError(f"Unsupported mesh format for rigging: {suffix}")

    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if not meshes:
        raise RuntimeError("No mesh objects were imported into Blender.")
    return meshes


def join_meshes(meshes: list[bpy.types.Object]) -> bpy.types.Object:
    for obj in bpy.context.selected_objects:
        obj.select_set(False)

    for obj in meshes:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]

    if len(meshes) > 1:
        bpy.ops.object.join()

    mesh = bpy.context.view_layer.objects.active
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")
    for polygon in mesh.data.polygons:
        polygon.use_smooth = True
    return mesh


def mesh_bounds_world(mesh: bpy.types.Object) -> tuple[Vector, Vector]:
    corners = [mesh.matrix_world @ Vector(corner) for corner in mesh.bound_box]
    min_corner = Vector((min(point.x for point in corners), min(point.y for point in corners), min(point.z for point in corners)))
    max_corner = Vector((max(point.x for point in corners), max(point.y for point in corners), max(point.z for point in corners)))
    return min_corner, max_corner


def add_bone(
    armature: bpy.types.Object,
    *,
    name: str,
    head: tuple[float, float, float],
    tail: tuple[float, float, float],
    parent: bpy.types.Bone | None = None,
    connected: bool = False,
) -> bpy.types.EditBone:
    bone = armature.data.edit_bones.new(name)
    bone.head = head
    bone.tail = tail
    if parent is not None:
        bone.parent = parent
        bone.use_connect = connected
    return bone


def create_armature(mesh: bpy.types.Object, rig_name: str) -> bpy.types.Object:
    min_corner, max_corner = mesh_bounds_world(mesh)
    size = max_corner - min_corner
    height = max(size.z, 0.25)
    width = max(size.x, 0.18)
    depth = max(size.y, 0.12)
    center_x = (min_corner.x + max_corner.x) * 0.5
    center_y = (min_corner.y + max_corner.y) * 0.5
    floor_z = min_corner.z

    pelvis_z = floor_z + height * 0.53
    lower_spine_z = floor_z + height * 0.63
    upper_spine_z = floor_z + height * 0.76
    neck_z = floor_z + height * 0.88
    head_top_z = floor_z + height * 1.02
    shoulder_z = floor_z + height * 0.82
    elbow_z = floor_z + height * 0.67
    wrist_z = floor_z + height * 0.52
    hip_z = floor_z + height * 0.49
    knee_z = floor_z + height * 0.26
    ankle_z = floor_z + height * 0.06
    toe_z = floor_z + height * 0.02

    shoulder_offset = max(width * 0.23, 0.12)
    elbow_offset = max(width * 0.43, shoulder_offset + 0.1)
    wrist_offset = max(width * 0.62, elbow_offset + 0.1)
    hip_offset = max(width * 0.13, 0.06)
    foot_forward = max(depth * 0.28, 0.08)

    bpy.ops.object.armature_add(enter_editmode=True, location=(center_x, center_y, pelvis_z))
    armature = bpy.context.object
    armature.name = rig_name
    armature.data.name = f"{rig_name}Data"
    default_bone = armature.data.edit_bones[0]
    armature.data.edit_bones.remove(default_bone)

    root = add_bone(
        armature,
        name="root",
        head=(center_x, center_y, floor_z),
        tail=(center_x, center_y, pelvis_z),
    )
    pelvis = add_bone(
        armature,
        name="pelvis",
        head=(center_x, center_y, pelvis_z),
        tail=(center_x, center_y, lower_spine_z),
        parent=root,
        connected=True,
    )
    spine = add_bone(
        armature,
        name="spine",
        head=(center_x, center_y, lower_spine_z),
        tail=(center_x, center_y, upper_spine_z),
        parent=pelvis,
        connected=True,
    )
    chest = add_bone(
        armature,
        name="chest",
        head=(center_x, center_y, upper_spine_z),
        tail=(center_x, center_y, neck_z),
        parent=spine,
        connected=True,
    )
    neck = add_bone(
        armature,
        name="neck",
        head=(center_x, center_y, neck_z),
        tail=(center_x, center_y, floor_z + height * 0.94),
        parent=chest,
        connected=True,
    )
    add_bone(
        armature,
        name="head",
        head=tuple(neck.tail),
        tail=(center_x, center_y, head_top_z),
        parent=neck,
        connected=True,
    )

    for side_name, sign in (("L", 1.0), ("R", -1.0)):
        shoulder = add_bone(
            armature,
            name=f"upper_arm.{side_name}",
            head=(center_x + shoulder_offset * sign, center_y, shoulder_z),
            tail=(center_x + elbow_offset * sign, center_y, elbow_z),
            parent=chest,
        )
        forearm = add_bone(
            armature,
            name=f"forearm.{side_name}",
            head=tuple(shoulder.tail),
            tail=(center_x + wrist_offset * sign, center_y, wrist_z),
            parent=shoulder,
            connected=True,
        )
        add_bone(
            armature,
            name=f"hand.{side_name}",
            head=tuple(forearm.tail),
            tail=(center_x + (wrist_offset + 0.08) * sign, center_y, wrist_z - 0.02),
            parent=forearm,
            connected=True,
        )

        thigh = add_bone(
            armature,
            name=f"thigh.{side_name}",
            head=(center_x + hip_offset * sign, center_y, hip_z),
            tail=(center_x + hip_offset * sign, center_y, knee_z),
            parent=pelvis,
        )
        shin = add_bone(
            armature,
            name=f"shin.{side_name}",
            head=tuple(thigh.tail),
            tail=(center_x + hip_offset * sign, center_y, ankle_z),
            parent=thigh,
            connected=True,
        )
        foot = add_bone(
            armature,
            name=f"foot.{side_name}",
            head=tuple(shin.tail),
            tail=(center_x + hip_offset * sign, center_y + foot_forward, toe_z),
            parent=shin,
            connected=True,
        )
        add_bone(
            armature,
            name=f"toe.{side_name}",
            head=tuple(foot.tail),
            tail=(center_x + hip_offset * sign, center_y + foot_forward * 1.35, toe_z),
            parent=foot,
            connected=True,
        )

    bpy.ops.object.mode_set(mode="OBJECT")
    armature["enya_rig_guide"] = {
        "center_x": center_x,
        "floor_z": floor_z,
        "height": height,
        "shoulder_offset": shoulder_offset,
        "elbow_offset": elbow_offset,
        "wrist_offset": wrist_offset,
        "hip_offset": hip_offset,
    }
    return armature


def _smoothstep(edge0: float, edge1: float, value: float) -> float:
    if edge0 == edge1:
        return 1.0 if value >= edge1 else 0.0
    t = max(0.0, min(1.0, (value - edge0) / (edge1 - edge0)))
    return t * t * (3.0 - 2.0 * t)


def _count_weighted_vertices(mesh: bpy.types.Object) -> int:
    return sum(1 for vertex in mesh.data.vertices if len(vertex.groups) > 0)


def _apply_procedural_weights(mesh: bpy.types.Object, armature: bpy.types.Object) -> None:
    guide = armature.get("enya_rig_guide")
    if not guide:
        raise RuntimeError("Rig guide metadata is missing from the armature.")

    center_x = float(guide["center_x"])
    floor_z = float(guide["floor_z"])
    height = max(float(guide["height"]), 0.25)
    shoulder_offset = max(float(guide["shoulder_offset"]), 0.12)
    elbow_offset = max(float(guide["elbow_offset"]), shoulder_offset + 0.1)
    wrist_offset = max(float(guide["wrist_offset"]), elbow_offset + 0.1)
    hip_offset = max(float(guide["hip_offset"]), 0.06)

    for group in list(mesh.vertex_groups):
        mesh.vertex_groups.remove(group)

    deform_groups = {
        bone.name: mesh.vertex_groups.new(name=bone.name)
        for bone in armature.data.bones
        if bone.use_deform
    }

    def assign(index: int, weights: dict[str, float]) -> None:
        total = sum(weight for weight in weights.values() if weight > 0.0)
        if total <= 0.0:
            deform_groups["pelvis"].add([index], 1.0, "REPLACE")
            return

        for name, weight in weights.items():
            if weight <= 0.0:
                continue
            deform_groups[name].add([index], weight / total, "REPLACE")

    for vertex in mesh.data.vertices:
        world = mesh.matrix_world @ vertex.co
        x_offset = world.x - center_x
        x_abs = abs(x_offset)
        vertical = max(0.0, min(1.05, (world.z - floor_z) / height))
        side = "L" if x_offset >= 0 else "R"

        arm_presence = _smoothstep(shoulder_offset * 0.8, wrist_offset * 0.92, x_abs) * _smoothstep(0.44, 0.68, vertical)
        leg_presence = _smoothstep(hip_offset * 0.5, shoulder_offset * 0.92, x_abs) * (1.0 - _smoothstep(0.58, 0.72, vertical))

        if arm_presence >= 0.45:
            arm_progress = max(0.0, min(1.0, (x_abs - shoulder_offset) / max(wrist_offset - shoulder_offset, 1e-3)))
            if arm_progress < 0.35:
                blend = arm_progress / 0.35
                assign(
                    vertex.index,
                    {
                        "chest": 1.0 - blend,
                        f"upper_arm.{side}": blend,
                    },
                )
            elif arm_progress < 0.78:
                blend = (arm_progress - 0.35) / 0.43
                assign(
                    vertex.index,
                    {
                        f"upper_arm.{side}": 1.0 - blend,
                        f"forearm.{side}": blend,
                    },
                )
            else:
                blend = min(1.0, (arm_progress - 0.78) / 0.22)
                assign(
                    vertex.index,
                    {
                        f"forearm.{side}": 1.0 - blend,
                        f"hand.{side}": blend,
                    },
                )
            continue

        if leg_presence >= 0.32:
            if vertical >= 0.46:
                blend = _smoothstep(0.46, 0.58, vertical)
                assign(
                    vertex.index,
                    {
                        "pelvis": blend,
                        f"thigh.{side}": 1.0 - blend,
                    },
                )
            elif vertical >= 0.24:
                blend = _smoothstep(0.24, 0.46, vertical)
                assign(
                    vertex.index,
                    {
                        f"shin.{side}": 1.0 - blend,
                        f"thigh.{side}": blend,
                    },
                )
            elif vertical >= 0.08:
                blend = _smoothstep(0.08, 0.24, vertical)
                assign(
                    vertex.index,
                    {
                        f"foot.{side}": 1.0 - blend,
                        f"shin.{side}": blend,
                    },
                )
            else:
                blend = _smoothstep(0.0, 0.08, vertical)
                assign(
                    vertex.index,
                    {
                        f"toe.{side}": 1.0 - blend,
                        f"foot.{side}": blend,
                    },
                )
            continue

        if vertical >= 0.96:
            assign(vertex.index, {"head": 1.0})
        elif vertical >= 0.9:
            blend = _smoothstep(0.9, 0.96, vertical)
            assign(vertex.index, {"neck": 1.0 - blend, "head": blend})
        elif vertical >= 0.78:
            blend = _smoothstep(0.78, 0.9, vertical)
            assign(vertex.index, {"chest": 1.0 - blend, "neck": blend})
        elif vertical >= 0.63:
            blend = _smoothstep(0.63, 0.78, vertical)
            assign(vertex.index, {"spine": 1.0 - blend, "chest": blend})
        elif vertical >= 0.52:
            blend = _smoothstep(0.52, 0.63, vertical)
            assign(vertex.index, {"pelvis": 1.0 - blend, "spine": blend})
        elif vertical >= 0.22:
            blend = _smoothstep(0.22, 0.52, vertical)
            assign(vertex.index, {"root": 1.0 - blend, "pelvis": blend})
        else:
            assign(vertex.index, {"root": 1.0})

    modifier = mesh.modifiers.get("Armature") or mesh.modifiers.new(name="Armature", type="ARMATURE")
    modifier.object = armature
    mesh.parent = armature
    mesh.matrix_parent_inverse = armature.matrix_world.inverted()
    print(f"Procedural skin weights assigned to {_count_weighted_vertices(mesh)} vertices.")


def bind_mesh(mesh: bpy.types.Object, armature: bpy.types.Object) -> None:
    for obj in bpy.context.selected_objects:
        obj.select_set(False)

    mesh.select_set(True)
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature

    try:
        bpy.ops.object.parent_set(type="ARMATURE_AUTO")
        print("Automatic armature weights applied.")
    except Exception as exc:
        print(f"Automatic weights failed, falling back to plain armature parenting: {exc}")
        bpy.ops.object.parent_set(type="ARMATURE_NAME")

    if _count_weighted_vertices(mesh) == 0:
        print("Automatic weights produced no usable skin data. Generating procedural weights instead.")
        _apply_procedural_weights(mesh, armature)


def export_outputs(mesh: bpy.types.Object, armature: bpy.types.Object, output_glb: Path, output_fbx: Path) -> None:
    output_glb.parent.mkdir(parents=True, exist_ok=True)
    output_fbx.parent.mkdir(parents=True, exist_ok=True)

    for obj in bpy.context.selected_objects:
        obj.select_set(False)
    mesh.select_set(True)
    armature.select_set(True)
    bpy.context.view_layer.objects.active = mesh

    bpy.ops.export_scene.gltf(
        filepath=str(output_glb),
        export_format="GLB",
        use_selection=True,
        export_apply=False,
        export_animations=False,
        export_normals=True,
        export_tangents=False,
        export_yup=True,
    )
    bpy.ops.export_scene.fbx(
        filepath=str(output_fbx),
        use_selection=True,
        add_leaf_bones=False,
        bake_anim=False,
        use_armature_deform_only=True,
        path_mode="AUTO",
    )


def main() -> None:
    args = parse_args()
    input_path = Path(args.input).resolve()
    output_glb = Path(args.output_glb).resolve()
    output_fbx = Path(args.output_fbx).resolve()

    if not input_path.exists():
        raise RuntimeError(f"Input mesh not found: {input_path}")

    clear_scene()
    imported_meshes = import_mesh(input_path)
    mesh = join_meshes(imported_meshes)
    armature = create_armature(mesh, args.rig_name)
    bind_mesh(mesh, armature)
    export_outputs(mesh, armature, output_glb, output_fbx)
    print(f"Rigged outputs written to {output_glb} and {output_fbx}")


if __name__ == "__main__":
    main()
