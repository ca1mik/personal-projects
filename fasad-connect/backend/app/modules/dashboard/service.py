from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.dashboard.schemas import DashboardSummary, MaterialStockCounter, StatusCounter
from app.modules.leads.models import Lead
from app.modules.order_statuses.models import OrderStatus
from app.modules.orders.models import Order
from app.modules.production.service import ProductionAnalyticsService
from app.modules.stock.models import StockItem


class DashboardService:
    @staticmethod
    def get_summary(db: Session) -> DashboardSummary:
        total_orders = int(db.scalar(select(func.count()).select_from(Order).where(Order.deleted_at.is_(None))) or 0)
        new_leads = int(
            db.scalar(select(func.count()).select_from(Lead).where(Lead.status == "new", Lead.deleted_at.is_(None))) or 0
        )
        mock_revenue = db.scalar(
            select(func.coalesce(func.sum(Order.final_amount), 0)).select_from(Order).where(Order.deleted_at.is_(None))
        ) or Decimal("0")

        status_rows = db.execute(
            select(OrderStatus.code, OrderStatus.name, func.count(Order.id))
            .select_from(OrderStatus)
            .join(Order, (Order.status_id == OrderStatus.id) & Order.deleted_at.is_(None), isouter=True)
            .group_by(OrderStatus.id)
            .order_by(OrderStatus.sort_order.asc())
        ).all()
        stock_rows = db.execute(
            select(StockItem.material_type, func.count(StockItem.id))
            .group_by(StockItem.material_type)
            .order_by(StockItem.material_type.asc())
        ).all()

        return DashboardSummary(
            total_orders=total_orders,
            new_leads=new_leads,
            mock_revenue=mock_revenue,
            orders_by_status=[
                StatusCounter(code=code, name=name, count=count)
                for code, name, count in status_rows
            ],
            stock_by_material_type=[
                MaterialStockCounter(material_type=material_type, count=count)
                for material_type, count in stock_rows
            ],
            production=ProductionAnalyticsService.get_dashboard(db),
        )
