from __future__ import annotations
import os
import secrets
from datetime import date,timedelta
from decimal import Decimal

from sqlalchemy import select
from app.db import base
from app.db.base_class import Base
from app.db.session import engine,SessionLocal
from app.core.security import hash_password
from app.modules.users.models import User
from app.modules.messaging.models import ChannelAccount
from app.modules.clients.models import Client
from app.modules.directions.service import DirectionService
from app.modules.directions.models import ProductionDirection
from app.modules.orders.service import OrderService
from app.modules.orders.schemas import OrderCreate,OrderPositionsReplace,OrderPositionWrite
from app.modules.orders.positions_service import OrderPositionService
from .store import store


def initialize(demo=False):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        has_users=db.scalar(select(User.id).limit(1)) is not None
    if not has_users:
        from scripts import seed
        seed.USERS=[(role,name,email,login,secrets.token_urlsafe(24)) for role,name,email,login,password in seed.USERS]
        seed.seed()
        with SessionLocal() as db:
            for u in db.scalars(select(User)).all():
                if u.role.code=='admin':u.login='owner';u.full_name='Владелец мастерской'
                else:u.is_active=False
            for channel in db.scalars(select(ChannelAccount)).all():channel.is_active=channel.code=='website_form_default'
            for code,name,suffix in [('pvc','ПВХ','П'),('enamel','Эмаль',''),('veneer','Шпон','Ш')]:
                if not DirectionService.get_by_code(db,code):db.add(ProductionDirection(code=code,name=name,number_suffix=suffix))
            db.commit()
    if demo and not store().get('demo_seeded'):
        with SessionLocal() as db:
            owner=db.scalar(select(User).where(User.login=='owner'))
            for i,(name,org,color,kind) in enumerate([
                ('Анна Смирнова','Кухни Север','Кашемир','pvc'),
                ('Михаил Орлов','Студия Линия','Белый матовый','enamel'),
                ('Елена Соколова','Мебельная мастерская','Графит','pvc')]):
                client=Client(full_name=name,organization=org,comment='Вымышленный клиент для демонстрации')
                db.add(client);db.commit();db.refresh(client)
                order=OrderService.create_order(db,OrderCreate(client_id=client.id,manager_id=owner.id,direction_code=kind,order_number=str(1041+i),due_date=date.today()+timedelta(days=4+i*3),comment='Демонстрационный заказ'),owner.id)
                rows=[OrderPositionWrite(name='Фасад '+color,kind='film' if kind=='pvc' else 'enamel',is_custom=True,unit='sqm',width=450,height=720,quantity=8+i*2,thickness=16,color=color,milling='Рамка',unit_price=3500+i*500),OrderPositionWrite(name='Фасад '+color,kind='film' if kind=='pvc' else 'enamel',is_custom=True,unit='sqm',width=600,height=140,quantity=4,thickness=16,color=color,milling='Рамка',unit_price=3500+i*500)]
                OrderPositionService.replace_positions(db,order.id,OrderPositionsReplace(positions=rows),owner.id)
        store().set('demo_seeded',True);store().set('owner_ready',True)
        store().event(None,'info','Подготовлены три вымышленных заказа для демонстрации')
    print('Workspace ready',flush=True)


if __name__=='__main__':initialize(os.environ.get('FASAD_CONNECT_DEMO')=='1')
