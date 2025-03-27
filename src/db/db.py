from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Order, UserTrade, UserTradeStatus
from cube.cube_types import OrderStatus

class Database:
    def __init__(self, db_url: str):
        self.engine = create_engine(db_url, connect_args={"check_same_thread": False})
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def get_db(self):
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def init_db(self):
        Base.metadata.create_all(bind=self.engine)

    def get_live_orders(self):
        with self.get_db() as db:
            return db.query(Order).filter(Order.status == OrderStatus.OPEN
                                          or Order.status == OrderStatus.PARTIALLY_FILLED).all()

    def get_active_trades(self):
        with self.get_db() as db:
            return db.query(UserTrade).filter(UserTrade.status == UserTradeStatus.ACTIVE
                                              or UserTrade.status == UserTradeStatus.PENDING).all()

    def update_order(self, order: Order):
        with self.get_db() as db:
            db.query(Order).filter(Order.client_order_id == order.client_order_id).update(order.model_dump())
            db.commit()

