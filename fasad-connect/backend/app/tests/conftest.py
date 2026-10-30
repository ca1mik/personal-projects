from __future__ import annotations

from collections.abc import Generator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.db.sqlite_unicode import install_unicode_case_functions
from app.main import app
from app.modules.order_statuses.models import OrderStatus
from app.modules.production.models import (
    EdgeMaterial,
    Hardware,
    Material,
    ProductionWorkflow,
    WorkCenter,
    WorkflowStage,
)
from app.modules.templates.models import ProductTemplate
from app.modules.users.models import Permission, Role, User

# Права и роли берём из того же места, что и боевой сид. Иначе тесты проверяют
# доступ у роли, которой нет ни у одного живого сотрудника: заказчик уже получил
# ситуацию, когда «оператор» в тестах ничего не мог, а оператор в цехе открывал
# деньги по заказам.
from scripts.seed import PERMISSIONS, ROLE_PERMISSION_MAP

SQLALCHEMY_DATABASE_URL = "sqlite+pysqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
# Тесты должны видеть тот же регистронезависимый поиск, что и прод.
install_unicode_case_functions(engine)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db() -> Generator[Session, None, None]:
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def seed_roles_and_permissions(db: Session) -> dict[str, Role]:
    """Заводит в тестовой БД те же права и роли, что раздаёт scripts/seed.py.

    Набор прав не дублируется руками: любое право, добавленное в сид, сразу
    попадает в тесты, и негативная проверка доступа перестаёт быть фикцией.
    """
    permissions = {code: Permission(code=code, name=name) for code, name in PERMISSIONS}
    db.add_all(list(permissions.values()))
    db.flush()

    roles: dict[str, Role] = {}
    for role_code, permission_codes in ROLE_PERMISSION_MAP.items():
        role = Role(
            code=role_code,
            name=role_code,
            description=f"Seeded role {role_code}",
            permissions=[permissions[code] for code in permission_codes],
        )
        db.add(role)
        roles[role_code] = role
    db.flush()
    return roles


def create_user_for_role(db: Session, role: Role, login: str, password: str) -> User:
    """Сотрудник с боевым набором прав своей роли — для проверок доступа."""
    user = User(
        full_name=f"{login} user",
        email=f"{login}@example.com",
        login=login,
        password_hash=hash_password(password),
        role_id=role.id,
        is_active=True,
    )
    db.add(user)
    db.commit()
    return user


def seed_reference_data(db: Session) -> None:
    roles = seed_roles_and_permissions(db)

    admin_user = User(
        full_name="Admin User",
        email="admin@example.com",
        login="admin",
        password_hash=hash_password("admin123"),
        role_id=roles["admin"].id,
        is_active=True,
    )
    db.add(admin_user)

    db.add(
        OrderStatus(code="new", name="New", sort_order=10, is_terminal=False),
    )
    db.add(OrderStatus(code="approved", name="Approved", sort_order=30, is_terminal=False))
    db.add(
        OrderStatus(code="manufacturing", name="Manufacturing", sort_order=70, is_terminal=False)
    )
    db.add(OrderStatus(code="ready", name="Ready", sort_order=80, is_terminal=False))

    db.add(
        Material(
            code="ldsp_white_18",
            name="LDSP White 18 mm",
            category="board",
            thickness=Decimal("18"),
            length=Decimal("2800"),
            width=Decimal("2070"),
            unit="sqm",
            color="white",
            texture_direction="horizontal",
            price=Decimal("950"),
            is_active=True,
        )
    )
    db.add(
        EdgeMaterial(
            code="edge_abs_white_2",
            name="ABS White 2 mm",
            thickness=Decimal("2"),
            color="white",
            unit="m",
            price=Decimal("32"),
            is_active=True,
        )
    )
    db.add(
        Hardware(
            code="shelf_pin",
            name="Shelf pin",
            unit="pcs",
            price=Decimal("4"),
            params_json={},
            is_active=True,
        )
    )
    db.add(
        Hardware(
            code="confirmat",
            name="Confirmat",
            unit="pcs",
            price=Decimal("6"),
            params_json={},
            is_active=True,
        )
    )
    db.add(
        Hardware(
            code="cam_lock",
            name="Cam lock",
            unit="pcs",
            price=Decimal("18"),
            params_json={},
            is_active=True,
        )
    )
    db.add(
        Hardware(
            code="leg_set",
            name="Cabinet leg",
            unit="pcs",
            price=Decimal("55"),
            params_json={},
            is_active=True,
        )
    )

    db.add(
        ProductTemplate(
            code="wardrobe_basic",
            name="Wardrobe Basic",
            category="wardrobe",
            description="Test template",
            is_active=True,
            formula_config_json={"strategy": "wardrobe_basic"},
        )
    )
    cutting_center = WorkCenter(
        code="cutting", name="Cutting Area", description="Cutting", is_active=True
    )
    assembly_center = WorkCenter(
        code="assembly", name="Assembly", description="Assembly", is_active=True
    )
    qc_center = WorkCenter(code="qc", name="Quality Control", description="QC", is_active=True)
    db.add_all([cutting_center, assembly_center, qc_center])
    db.flush()

    workflow = ProductionWorkflow(
        code="default_furniture_flow",
        name="Default Furniture Flow",
        description="Test production workflow",
        is_active=True,
        is_default=True,
    )
    db.add(workflow)
    db.flush()
    db.add_all(
        [
            WorkflowStage(
                workflow_id=workflow.id,
                work_center_id=cutting_center.id,
                code="cutting",
                name="Cutting",
                sort_order=10,
                auto_start_next=False,
                requires_photo=True,
                requires_comment=False,
                is_active=True,
            ),
            WorkflowStage(
                workflow_id=workflow.id,
                work_center_id=assembly_center.id,
                code="assembly",
                name="Assembly",
                sort_order=20,
                auto_start_next=False,
                requires_photo=False,
                requires_comment=False,
                is_active=True,
            ),
            WorkflowStage(
                workflow_id=workflow.id,
                work_center_id=qc_center.id,
                code="qc",
                name="Quality Control",
                sort_order=30,
                auto_start_next=False,
                requires_photo=True,
                requires_comment=True,
                is_active=True,
            ),
        ]
    )
    db.commit()


@pytest.fixture(autouse=True)
def setup_database():
    from app.core.config import get_settings

    previous_intake_secret = get_settings().public_intake_secret
    get_settings().public_intake_secret = "test-intake-secret"
    from app.core.intake_guard import IntakeGuard

    for middleware in app.user_middleware:
        if middleware.cls is IntakeGuard and app.middleware_stack is not None:
            current = app.middleware_stack
            while current is not None:
                if isinstance(current, IntakeGuard):
                    current.reset()
                    break
                current = getattr(current, "app", None)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    seed_reference_data(db)
    db.close()
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()
    get_settings().public_intake_secret = previous_intake_secret


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        test_client.headers["X-Fasad-Webhook-Token"] = "test-intake-secret"
        yield test_client


@pytest.fixture
def auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"login": "admin", "password": "admin123"})
    token = response.json()["data"]["token"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Direct session on the test database, for asserting persisted state."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def login_headers(client: TestClient, login: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"login": login, "password": password})
    token = response.json()["data"]["token"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _role_headers(client: TestClient, db: Session, role_code: str) -> dict[str, str]:
    role = db.scalars(select(Role).where(Role.code == role_code)).one()
    password = f"{role_code}123"
    create_user_for_role(db, role, role_code, password)
    return login_headers(client, role_code, password)


@pytest.fixture
def manager_auth_headers(client: TestClient, db_session: Session) -> dict[str, str]:
    """Менеджер: заявки, клиенты, заказы и деньги. Цех только смотрит."""
    return _role_headers(client, db_session, "manager")


@pytest.fixture
def technologist_auth_headers(client: TestClient, db_session: Session) -> dict[str, str]:
    """Технолог: справочники изделий, склад, производство."""
    return _role_headers(client, db_session, "technologist")


@pytest.fixture
def operator_auth_headers(client: TestClient, db_session: Session) -> dict[str, str]:
    """Работник цеха с боевым набором прав роли operator из seed.py.

    Раньше здесь заводилась роль без единого права, и негативные проверки
    доступа ничего не проверяли: живой оператор с production.* получал 200 там,
    где тест ожидал отказ.
    """
    return _role_headers(client, db_session, "operator")


@pytest.fixture
def no_permission_auth_headers(client: TestClient, db_session: Session) -> dict[str, str]:
    """Сотрудник с ролью без прав: так выглядит новая роль сразу после создания."""
    role = Role(code="rookie", name="Rookie", description="Новая роль без прав")
    db_session.add(role)
    db_session.flush()
    create_user_for_role(db_session, role, "rookie", "rookie123")
    return login_headers(client, "rookie", "rookie123")
