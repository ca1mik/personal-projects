from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.security import hash_password
from app.db import base  # noqa: F401
from app.db.session import SessionLocal
from app.modules.messaging.models import ChannelAccount
from app.modules.order_statuses.models import OrderStatus
from app.modules.production.models import (
    EdgeMaterial,
    Hardware,
    Material,
    ProductionWorkflow,
    WorkCenter,
    WorkflowStage,
)
from app.modules.stock.models import StockItem
from app.modules.templates.models import ProductTemplate
from app.modules.users.models import Permission, Role, User

# Названия прав — по-русски и по делу: их читает не программист, а тот, кто
# раздаёт доступы. «Manage leads» ничего не говорит о том, что человек сможет
# завести заявку и увидеть телефоны клиентов.
PERMISSIONS = [
    ("dashboard.read", "Смотреть сводку"),
    # Отчёты отдельно от сводки: это выручка, объёмы и активность клиентов.
    # Пока отчёты открывались правом на сводку, работник цеха видел деньги
    # студии и выгружал клиентскую базу в Excel — при описании роли «денег и
    # клиентов не видит».
    ("reports.read", "Смотреть отчёты и выгрузки"),
    ("messaging.read", "Читать диалоги"),
    ("messaging.reply", "Отвечать в диалогах"),
    ("channels.manage", "Настраивать каналы связи"),
    ("production.read", "Видеть работу цеха"),
    ("production.execute", "Отчитываться по этапам в цехе"),
    ("users.manage", "Заводить сотрудников"),
    ("roles.manage", "Настраивать роли"),
    ("permissions.manage", "Настраивать права"),
    ("audit.read", "Смотреть журнал действий"),
    ("clients.manage", "Вести клиентов"),
    ("leads.manage", "Принимать заявки"),
    ("orders.manage", "Вести заказы и деньги"),
    ("templates.manage", "Править справочники изделий"),
    ("production.manage", "Управлять производством"),
    ("stock.manage", "Вести склад"),
]

ROLE_PERMISSION_MAP = {
    "admin": [item[0] for item in PERMISSIONS],
    "manager": [
        "dashboard.read",
        "reports.read",
        "messaging.read",
        "messaging.reply",
        "clients.manage",
        "leads.manage",
        "orders.manage",
        "production.read",
    ],
    "technologist": [
        "dashboard.read",
        "reports.read",
        "messaging.read",
        "orders.manage",
        "templates.manage",
        "production.read",
        "production.execute",
        "production.manage",
        "stock.manage",
    ],
    # Работнику цеха сводка нужна — там его этапы и брак, — а отчёты нет.
    "operator": [
        "dashboard.read",
        "production.read",
        "production.execute",
    ],
}

CHANNEL_ACCOUNTS = [
    {
        "code": "website_form_default",
        "channel_type": "website_form",
        "name": "Website Form",
        "description": "Основной прием заявок с сайта.",
        "inbound_mode": "form_post",
        "is_active": True,
        "default_manager_login": "manager",
        "config_json": {"public_form": True},
    },
    {
        "code": "email_sales",
        "channel_type": "email",
        "name": "Sales Email",
        "description": "Почтовый ящик отдела продаж для приема заявок.",
        "inbound_mode": "polling",
        "is_active": True,
        "default_manager_login": "manager",
        # Empty hosts on purpose: the scheduler skips accounts without IMAP
        # credentials, so the seeded channel stays inert until an admin fills
        # it in on /admin/channels. Never seed real mailbox credentials.
        "config_json": {
            "imap": {"host": "", "port": 993, "ssl": True, "login": "", "folder": "INBOX"},
            "smtp": {
                "host": "",
                "port": 465,
                "security": "ssl",
                "login": "",
                "from_email": "",
                "from_name": "",
            },
            "poll_interval_seconds": 120,
            "since_days": 3,
            "unseen_only": True,
            "mark_seen": True,
        },
    },
    {
        "code": "telegram_main_bot",
        "channel_type": "telegram_bot",
        "name": "Telegram Bot",
        "description": "Основной Telegram-бот приёма заявок и предварительного расчёта.",
        "inbound_mode": "webhook",
        "is_active": True,
        "default_manager_login": "manager",
        "config_json": {"bot_username": "@fasad_demo_bot"},
    },
    {
        "code": "telegram_operator_chat",
        "channel_type": "telegram",
        "name": "Telegram Direct",
        "description": "Входящие сообщения из Telegram без бот-сценария.",
        "inbound_mode": "webhook",
        "is_active": True,
        "default_manager_login": "manager",
        "config_json": {"mode": "direct"},
    },
    {
        "code": "whatsapp_business_main",
        "channel_type": "whatsapp",
        "name": "WhatsApp Business",
        "description": "Основной канал WhatsApp для клиентов.",
        "inbound_mode": "webhook",
        "is_active": True,
        "default_manager_login": "manager",
        "config_json": {"provider": "meta_cloud_api"},
    },
    {
        "code": "generic_webhook_default",
        "channel_type": "webhook",
        "name": "Generic Webhook",
        "description": "Внешние лид-формы и партнерские источники.",
        "inbound_mode": "webhook",
        "is_active": True,
        "default_manager_login": "manager",
        "config_json": {"auth_mode": "shared_secret"},
    },
    {
        "code": "manual_manager_default",
        "channel_type": "manual_manager_input",
        "name": "Manual Manager Input",
        "description": "Ручной ввод заявок менеджером.",
        "inbound_mode": "manual",
        "is_active": True,
        "default_manager_login": "manager",
        "config_json": {"ui_entry": True},
    },
]

ORDER_STATUSES = [
    ("new", "Новый", 10, False),
    ("calculating", "Расчёт", 20, False),
    ("approved", "Согласован", 30, False),
    ("paid", "Оплачен", 40, False),
    ("cutting", "Раскрой", 50, False),
    ("cnc", "ЧПУ", 60, False),
    ("waiting_client", "Ждём ответа клиента", 25, False),
    ("accepted", "Принят в работу", 35, False),
    ("manufacturing", "В производстве", 70, False),
    ("ready", "Готов", 80, False),
    ("shipped", "Отгружен", 90, True),
    ("cancelled", "Отменён", 100, True),
]

MATERIALS = [
    {
        "code": "ldsp_white_18",
        "name": "ЛДСП белая 18 мм",
        "category": "board",
        "thickness": Decimal("18"),
        "length": Decimal("2800"),
        "width": Decimal("2070"),
        "unit": "sqm",
        "color": "white",
        "texture_direction": "horizontal",
        "price": Decimal("950"),
        "is_active": True,
    },
    {
        "code": "mdf_oak_16",
        "name": "МДФ дуб 16 мм",
        "category": "facade",
        "thickness": Decimal("16"),
        "length": Decimal("2800"),
        "width": Decimal("1220"),
        "unit": "sqm",
        "color": "oak",
        "texture_direction": "vertical",
        "price": Decimal("1450"),
        "is_active": True,
    },
]

EDGE_MATERIALS = [
    {
        "code": "edge_abs_white_2",
        "name": "Кромка ABS белая 2 мм",
        "thickness": Decimal("2"),
        "color": "white",
        "unit": "m",
        "price": Decimal("32"),
        "is_active": True,
    },
    {
        "code": "edge_abs_oak_1",
        "name": "Кромка ABS дуб 1 мм",
        "thickness": Decimal("1"),
        "color": "oak",
        "unit": "m",
        "price": Decimal("24"),
        "is_active": True,
    },
]

HARDWARE = [
    {
        "code": "shelf_pin",
        "name": "Полкодержатель",
        "unit": "pcs",
        "price": Decimal("4.5"),
        "params_json": {"diameter": 5},
        "is_active": True,
    },
    {
        "code": "confirmat",
        "name": "Конфирмат",
        "unit": "pcs",
        "price": Decimal("6.0"),
        "params_json": {"length": 50},
        "is_active": True,
    },
    {
        "code": "cam_lock",
        "name": "Эксцентриковая стяжка",
        "unit": "pcs",
        "price": Decimal("18.0"),
        "params_json": {"system": "minifix"},
        "is_active": True,
    },
    {
        "code": "leg_set",
        "name": "Опора мебельная",
        "unit": "pcs",
        "price": Decimal("55.0"),
        "params_json": {"height_mm": 100},
        "is_active": True,
    },
]

TEMPLATES = [
    {
        "code": "wardrobe_basic",
        "name": "Шкаф базовый",
        "category": "wardrobe",
        "description": "Базовый прямой шкаф с упрощенной формулой корпуса.",
        "is_active": True,
        "formula_config_json": {
            "version": 1,
            "strategy": "wardrobe_basic",
            "defaults": {"thickness": 18},
            "hardware_rules": {"shelf_pin": 4, "confirmat": 8},
        },
    },
    {
        "code": "kitchen_module_basic",
        "name": "Кухонный модуль базовый",
        "category": "kitchen",
        "description": "Базовый нижний кухонный модуль для MVP генератора деталей.",
        "is_active": True,
        "formula_config_json": {
            "version": 1,
            "strategy": "kitchen_module_basic",
            "defaults": {"thickness": 18},
            "hardware_rules": {"cam_lock": 8, "leg_set": 4},
        },
    },
]

USERS = [
    ("admin", "Admin User", "admin@example.com", "admin", "admin123"),
    ("manager", "Manager User", "manager@example.com", "manager", "manager123"),
    ("technologist", "Technologist User", "tech@example.com", "technologist", "tech123"),
    ("operator", "Cutting Operator", "cutting@example.com", "operator.cutting", "operator123"),
    ("operator", "Assembly Operator", "assembly@example.com", "operator.assembly", "operator123"),
]

WORK_CENTERS = [
    {
        "code": "cutting",
        "name": "Участок раскроя",
        "description": "Раскрой и первичная подготовка деталей.",
        "is_active": True,
    },
    {
        "code": "edge_banding",
        "name": "Участок кромления",
        "description": "Кромление и подготовка торцов.",
        "is_active": True,
    },
    {
        "code": "cnc",
        "name": "Участок ЧПУ",
        "description": "Сверление и обработка на ЧПУ.",
        "is_active": True,
    },
    {
        "code": "assembly",
        "name": "Участок сборки",
        "description": "Сборка и комплектование.",
        "is_active": True,
    },
    {
        "code": "qc",
        "name": "Контроль качества",
        "description": "Контроль качества и финальная проверка.",
        "is_active": True,
    },
    {
        "code": "packing",
        "name": "Участок упаковки",
        "description": "Упаковка и подготовка к отгрузке.",
        "is_active": True,
    },
]

PRODUCTION_WORKFLOWS = [
    {
        "code": "default_furniture_flow",
        "name": "Базовый маршрут производства",
        "description": "Базовый маршрут производства для мебельных заказов MVP.",
        "is_active": True,
        "is_default": True,
        "stages": [
            {
                "code": "cutting",
                "name": "Раскрой",
                "sort_order": 10,
                "work_center_code": "cutting",
                "auto_start_next": False,
                "requires_photo": True,
                "requires_comment": False,
                "is_active": True,
            },
            {
                "code": "edge_banding",
                "name": "Участок кромления",
                "sort_order": 20,
                "work_center_code": "edge_banding",
                "auto_start_next": False,
                "requires_photo": False,
                "requires_comment": False,
                "is_active": True,
            },
            {
                "code": "cnc",
                "name": "ЧПУ",
                "sort_order": 30,
                "work_center_code": "cnc",
                "auto_start_next": False,
                "requires_photo": False,
                "requires_comment": False,
                "is_active": True,
            },
            {
                "code": "assembly",
                "name": "Участок сборки",
                "sort_order": 40,
                "work_center_code": "assembly",
                "auto_start_next": False,
                "requires_photo": False,
                "requires_comment": False,
                "is_active": True,
            },
            {
                "code": "qc",
                "name": "Контроль качества",
                "sort_order": 50,
                "work_center_code": "qc",
                "auto_start_next": False,
                "requires_photo": True,
                "requires_comment": True,
                "is_active": True,
            },
            {
                "code": "packing",
                "name": "Участок упаковки",
                "sort_order": 60,
                "work_center_code": "packing",
                "auto_start_next": False,
                "requires_photo": False,
                "requires_comment": False,
                "is_active": True,
            },
        ],
    }
]


def upsert_permission(session, code: str, name: str) -> Permission:
    permission = session.scalar(select(Permission).where(Permission.code == code))
    if permission:
        permission.name = name
        return permission
    permission = Permission(code=code, name=name)
    session.add(permission)
    session.flush()
    return permission


def upsert_role(
    session, code: str, name: str, description: str, permission_codes: list[str]
) -> Role:
    role = session.scalar(
        select(Role).options(selectinload(Role.permissions)).where(Role.code == code)
    )
    permissions = session.scalars(
        select(Permission).where(Permission.code.in_(permission_codes))
    ).all()
    if role:
        role.name = name
        role.description = description
        role.permissions = permissions
        return role
    role = Role(code=code, name=name, description=description, permissions=permissions)
    session.add(role)
    session.flush()
    return role


def upsert_user(
    session, role_code: str, full_name: str, email: str, login: str, password: str
) -> User:
    role = session.scalar(select(Role).where(Role.code == role_code))
    user = session.scalar(select(User).where(User.login == login))
    if user:
        # Rerunning a seed must never restore a known demo password or reactivate
        # an account that an administrator deliberately disabled.
        return user
    user = User(
        full_name=full_name,
        email=email,
        login=login,
        password_hash=hash_password(password),
        role_id=role.id,
        is_active=True,
    )
    session.add(user)
    session.flush()
    return user


def upsert_model_by_code(session, model, payload: dict):
    entity = session.scalar(select(model).where(model.code == payload["code"]))
    if entity:
        for key, value in payload.items():
            setattr(entity, key, value)
        return entity
    entity = model(**payload)
    session.add(entity)
    session.flush()
    return entity


def upsert_order_status(session, payload: tuple[str, str, int, bool]) -> OrderStatus:
    code, name, sort_order, is_terminal = payload
    status = session.scalar(select(OrderStatus).where(OrderStatus.code == code))
    if status:
        status.name = name
        status.sort_order = sort_order
        status.is_terminal = is_terminal
        return status
    status = OrderStatus(code=code, name=name, sort_order=sort_order, is_terminal=is_terminal)
    session.add(status)
    session.flush()
    return status


def upsert_work_center(session, payload: dict) -> WorkCenter:
    entity = session.scalar(select(WorkCenter).where(WorkCenter.code == payload["code"]))
    if entity:
        for key, value in payload.items():
            setattr(entity, key, value)
        return entity
    entity = WorkCenter(**payload)
    session.add(entity)
    session.flush()
    return entity


def upsert_workflow(session, payload: dict) -> ProductionWorkflow:
    workflow = session.scalar(
        select(ProductionWorkflow)
        .options(selectinload(ProductionWorkflow.stages))
        .where(ProductionWorkflow.code == payload["code"])
    )
    if payload.get("is_default"):
        for existing in session.scalars(
            select(ProductionWorkflow).where(ProductionWorkflow.code != payload["code"])
        ).all():
            existing.is_default = False

    if workflow:
        workflow.name = payload["name"]
        workflow.description = payload.get("description")
        workflow.is_active = payload.get("is_active", True)
        workflow.is_default = payload.get("is_default", False)
    else:
        workflow = ProductionWorkflow(
            code=payload["code"],
            name=payload["name"],
            description=payload.get("description"),
            is_active=payload.get("is_active", True),
            is_default=payload.get("is_default", False),
        )
        session.add(workflow)
        session.flush()

    active_codes: set[str] = set()
    existing_stages = {stage.code: stage for stage in workflow.stages}
    for stage_payload in payload["stages"]:
        active_codes.add(stage_payload["code"])
        work_center = session.scalar(
            select(WorkCenter).where(WorkCenter.code == stage_payload["work_center_code"])
        )
        stage = existing_stages.get(stage_payload["code"])
        values = {
            "workflow_id": workflow.id,
            "work_center_id": work_center.id if work_center else None,
            "code": stage_payload["code"],
            "name": stage_payload["name"],
            "sort_order": stage_payload["sort_order"],
            "auto_start_next": stage_payload.get("auto_start_next", False),
            "requires_photo": stage_payload.get("requires_photo", False),
            "requires_comment": stage_payload.get("requires_comment", False),
            "is_active": stage_payload.get("is_active", True),
        }
        if stage:
            for key, value in values.items():
                setattr(stage, key, value)
        else:
            session.add(WorkflowStage(**values))

    for stage in workflow.stages:
        if stage.code not in active_codes:
            stage.is_active = False

    session.flush()
    return workflow


def upsert_channel_account(session, payload: dict) -> ChannelAccount:
    account = session.scalar(select(ChannelAccount).where(ChannelAccount.code == payload["code"]))
    default_manager = session.scalar(
        select(User).where(User.login == payload.get("default_manager_login"))
    )
    values = {
        "channel_type": payload["channel_type"],
        "name": payload["name"],
        "description": payload.get("description"),
        "inbound_mode": payload.get("inbound_mode", "webhook"),
        "is_active": payload.get("is_active", True),
        "default_manager_id": default_manager.id if default_manager else None,
        "config_json": payload.get("config_json", {}),
    }
    if account:
        for key, value in values.items():
            setattr(account, key, value)
        return account
    account = ChannelAccount(code=payload["code"], **values)
    session.add(account)
    session.flush()
    return account


def seed() -> None:
    with SessionLocal() as session:
        if session.scalar(select(User.id).limit(1)) is not None:
            print("Seed skipped: users already exist. Existing installation is unchanged.")
            return
        for code, name in PERMISSIONS:
            upsert_permission(session, code, name)
        session.flush()

        # Названия ролей по-русски и описание словами того, кто их раздаёт:
        # «Administrator / Worker execution role» админу студии ничего не
        # объясняет.
        upsert_role(
            session,
            "admin",
            "Администратор",
            "Полный доступ: сотрудники, права, справочники, деньги, цех.",
            ROLE_PERMISSION_MAP["admin"],
        )
        upsert_role(
            session,
            "manager",
            "Менеджер",
            "Принимает заявки, ведёт клиентов, заказы и деньги. Цех только смотрит.",
            ROLE_PERMISSION_MAP["manager"],
        )
        upsert_role(
            session,
            "technologist",
            "Технолог",
            "Готовит производство: раскрой, справочники изделий, склад, этапы в цехе.",
            ROLE_PERMISSION_MAP["technologist"],
        )

        upsert_role(
            session,
            "operator",
            "Работник цеха",
            "Отчитывается по своим этапам. Денег и клиентов не видит.",
            ROLE_PERMISSION_MAP["operator"],
        )

        for role_code, full_name, email, login, password in USERS:
            upsert_user(session, role_code, full_name, email, login, password)

        for payload in CHANNEL_ACCOUNTS:
            upsert_channel_account(session, payload)

        for payload in ORDER_STATUSES:
            upsert_order_status(session, payload)

        # Рабочие материалы, цвета и изделия вносит студия. Демонстрационные
        # записи нельзя восстанавливать после очистки базы повторным seed.
        for payload in WORK_CENTERS:
            upsert_work_center(session, payload)
        for payload in PRODUCTION_WORKFLOWS:
            upsert_workflow(session, payload)

        session.commit()
        print("Seed completed.")


if __name__ == "__main__":
    seed()
