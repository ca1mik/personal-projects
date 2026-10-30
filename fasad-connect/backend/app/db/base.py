from app.db.base_class import Base
from app.modules.audit.models import AuditLog
from app.modules.clients.models import Client, ClientDepositMovement
from app.modules.cnc.models import CncJob, CncMachine
from app.modules.cutting_export.models import Export
from app.modules.directions.models import ProductionDirection
from app.modules.documents.models import Document
from app.modules.leads.models import Lead, LeadAttachment
from app.modules.messaging.models import (
    ChannelAccount,
    Conversation,
    Message,
    MessageAttachment,
    TelegramBotSession,
)
from app.modules.order_statuses.models import OrderStatus, OrderStatusHistory
from app.modules.orders.models import Order, OrderItem, OrderPayment, OrderPosition
from app.modules.parts_generator.models import Part, PartEdge, PartOperation
from app.modules.price_book.models import PriceItem, PriceItemChange
from app.modules.production.models import (
    EdgeMaterial,
    Hardware,
    Material,
    OrderStageInstance,
    ProductionWorkflow,
    StageAssignment,
    StageEvidence,
    WorkCenter,
    WorkflowStage,
)
from app.modules.stock.models import StockItem, StockMovement
from app.modules.shared.numbering import DocumentCounter
from app.modules.templates.models import ProductTemplate
from app.modules.users.models import Permission, Role, RolePermission, User

__all__ = [
    "AuditLog",
    "Base",
    "Client",
    "ClientDepositMovement",
    "CncJob",
    "CncMachine",
    "ChannelAccount",
    "Document",
    "DocumentCounter",
    "EdgeMaterial",
    "Export",
    "Hardware",
    "Lead",
    "LeadAttachment",
    "Material",
    "Conversation",
    "Message",
    "MessageAttachment",
    "OrderStageInstance",
    "Order",
    "OrderItem",
    "OrderPayment",
    "OrderPosition",
    "OrderStatus",
    "OrderStatusHistory",
    "Part",
    "PartEdge",
    "PartOperation",
    "Permission",
    "PriceItem",
    "PriceItemChange",
    "ProductTemplate",
    "ProductionDirection",
    "ProductionWorkflow",
    "Role",
    "RolePermission",
    "StageAssignment",
    "StageEvidence",
    "StockItem",
    "StockMovement",
    "TelegramBotSession",
    "User",
    "WorkCenter",
    "WorkflowStage",
]
