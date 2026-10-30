from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

THICKNESS_FALLBACK = Decimal("18")


@dataclass(slots=True)
class EdgeSpec:
    side: str
    length_mm: Decimal


@dataclass(slots=True)
class OperationSpec:
    operation_type: str
    x: Decimal | None = None
    y: Decimal | None = None
    z: Decimal | None = None
    diameter: Decimal | None = None
    depth: Decimal | None = None
    width: Decimal | None = None
    height: Decimal | None = None
    angle: Decimal | None = None
    params_json: dict = field(default_factory=dict)


@dataclass(slots=True)
class PartSpec:
    code: str
    name: str
    length: Decimal
    width: Decimal
    thickness: Decimal
    quantity: int
    grain_direction: str | None = None
    rotation_allowed: bool = True
    edges: list[EdgeSpec] = field(default_factory=list)
    operations: list[OperationSpec] = field(default_factory=list)


@dataclass(slots=True)
class GenerationBlueprint:
    parts: list[PartSpec]
    hardware_requirements: dict[str, Decimal]
    base_work_cost: Decimal


def _visible_front(length_mm: Decimal) -> list[EdgeSpec]:
    return [EdgeSpec(side="L1", length_mm=length_mm)]


def wardrobe_basic(
    *,
    width: Decimal,
    height: Decimal,
    depth: Decimal,
    quantity: int,
    thickness: Decimal | None = None,
) -> GenerationBlueprint:
    body = thickness or THICKNESS_FALLBACK
    inner_width = max(width - (body * 2), Decimal("100"))
    shelf_depth = max(depth - Decimal("20"), Decimal("120"))

    parts = [
        PartSpec(
            code="SIDE-L",
            name="Side left",
            length=height,
            width=depth,
            thickness=body,
            quantity=quantity,
            grain_direction="vertical",
            edges=_visible_front(height),
            operations=[
                OperationSpec(
                    "drill",
                    x=Decimal("37"),
                    y=Decimal("100"),
                    diameter=Decimal("5"),
                    depth=Decimal("12"),
                ),
                OperationSpec(
                    "drill",
                    x=Decimal("37"),
                    y=height - Decimal("100"),
                    diameter=Decimal("5"),
                    depth=Decimal("12"),
                ),
            ],
        ),
        PartSpec(
            code="SIDE-R",
            name="Side right",
            length=height,
            width=depth,
            thickness=body,
            quantity=quantity,
            grain_direction="vertical",
            edges=_visible_front(height),
            operations=[
                OperationSpec(
                    "drill",
                    x=Decimal("37"),
                    y=Decimal("100"),
                    diameter=Decimal("5"),
                    depth=Decimal("12"),
                ),
                OperationSpec(
                    "drill",
                    x=Decimal("37"),
                    y=height - Decimal("100"),
                    diameter=Decimal("5"),
                    depth=Decimal("12"),
                ),
            ],
        ),
        PartSpec(
            code="TOP",
            name="Top panel",
            length=inner_width,
            width=depth,
            thickness=body,
            quantity=quantity,
            grain_direction="horizontal",
            edges=_visible_front(inner_width),
        ),
        PartSpec(
            code="BOTTOM",
            name="Bottom panel",
            length=inner_width,
            width=depth,
            thickness=body,
            quantity=quantity,
            grain_direction="horizontal",
            edges=_visible_front(inner_width),
        ),
        PartSpec(
            code="SHELF",
            name="Inner shelf",
            length=inner_width,
            width=shelf_depth,
            thickness=body,
            quantity=quantity,
            grain_direction="horizontal",
            edges=_visible_front(inner_width),
        ),
    ]
    return GenerationBlueprint(
        parts=parts,
        hardware_requirements={
            "shelf_pin": Decimal(4 * quantity),
            "confirmat": Decimal(8 * quantity),
        },
        base_work_cost=Decimal("1800") * quantity,
    )


def kitchen_module_basic(
    *,
    width: Decimal,
    height: Decimal,
    depth: Decimal,
    quantity: int,
    thickness: Decimal | None = None,
) -> GenerationBlueprint:
    body = thickness or THICKNESS_FALLBACK
    inner_width = max(width - (body * 2), Decimal("100"))
    rail_width = Decimal("100")

    parts = [
        PartSpec(
            code="SIDE-L",
            name="Side left",
            length=height,
            width=depth,
            thickness=body,
            quantity=quantity,
            grain_direction="vertical",
            edges=_visible_front(height),
            operations=[
                OperationSpec(
                    "drill",
                    x=Decimal("37"),
                    y=Decimal("64"),
                    diameter=Decimal("5"),
                    depth=Decimal("12"),
                ),
                OperationSpec(
                    "drill",
                    x=Decimal("37"),
                    y=height - Decimal("64"),
                    diameter=Decimal("5"),
                    depth=Decimal("12"),
                ),
            ],
        ),
        PartSpec(
            code="SIDE-R",
            name="Side right",
            length=height,
            width=depth,
            thickness=body,
            quantity=quantity,
            grain_direction="vertical",
            edges=_visible_front(height),
            operations=[
                OperationSpec(
                    "drill",
                    x=Decimal("37"),
                    y=Decimal("64"),
                    diameter=Decimal("5"),
                    depth=Decimal("12"),
                ),
                OperationSpec(
                    "drill",
                    x=Decimal("37"),
                    y=height - Decimal("64"),
                    diameter=Decimal("5"),
                    depth=Decimal("12"),
                ),
            ],
        ),
        PartSpec(
            code="BOTTOM",
            name="Bottom panel",
            length=inner_width,
            width=depth,
            thickness=body,
            quantity=quantity,
            grain_direction="horizontal",
            edges=_visible_front(inner_width),
        ),
        PartSpec(
            code="SHELF",
            name="Shelf",
            length=inner_width,
            width=depth - Decimal("20"),
            thickness=body,
            quantity=quantity,
            grain_direction="horizontal",
            edges=_visible_front(inner_width),
        ),
        PartSpec(
            code="RAIL-F",
            name="Front rail",
            length=inner_width,
            width=rail_width,
            thickness=body,
            quantity=quantity,
        ),
        PartSpec(
            code="RAIL-R",
            name="Rear rail",
            length=inner_width,
            width=rail_width,
            thickness=body,
            quantity=quantity,
        ),
    ]
    return GenerationBlueprint(
        parts=parts,
        hardware_requirements={"cam_lock": Decimal(8 * quantity), "leg_set": Decimal(4 * quantity)},
        base_work_cost=Decimal("1500") * quantity,
    )


def build_blueprint(
    template_code: str,
    *,
    width: Decimal,
    height: Decimal,
    depth: Decimal,
    quantity: int,
    thickness: Decimal | None = None,
) -> GenerationBlueprint:
    match template_code:
        case "wardrobe_basic":
            return wardrobe_basic(
                width=width, height=height, depth=depth, quantity=quantity, thickness=thickness
            )
        case "kitchen_module_basic":
            return kitchen_module_basic(
                width=width,
                height=height,
                depth=depth,
                quantity=quantity,
                thickness=thickness,
            )
        case _:
            return wardrobe_basic(
                width=width, height=height, depth=depth, quantity=quantity, thickness=thickness
            )
