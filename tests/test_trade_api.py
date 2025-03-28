import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
from datetime import datetime
import uuid
import os
import tempfile
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from cube_dca.api.trade_api import router
from cube_dca.db.models import UserTrade, Order, UserTradeStatus, OrderStatus, Base
from fastapi import FastAPI, Depends
from cube_dca.db.db import Database
from cube_dca.external.cube.types import Market

# Test data constants
TEST_SYMBOL = "BTCUSDC"
TEST_SIDE = "buy"
TEST_QUANTITY = 1.0
TEST_PRICE = 50000.0

# Set up test database in a temp file
@pytest.fixture(scope="function")
def test_db():
    # Create a temp file for SQLite
    db_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    db_file.close()
    
    # Create database URL 
    db_url = f"sqlite:///{db_file.name}"
    
    # Create engine with shared connection pool
    engine = create_engine(
        db_url, 
        connect_args={"check_same_thread": False},
        poolclass=StaticPool  # Use static pool to ensure same connection is reused
    )
    
    # Create all tables
    Base.metadata.create_all(engine)
    
    # Create session factory 
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Create Database instance
    db = Database(db_url)
    db.engine = engine
    db.SessionLocal = SessionLocal
    
    # Return the database instance
    yield db
    
    # Clean up - close connections and remove temp file
    engine.dispose()
    os.unlink(db_file.name)

@pytest.fixture
def test_app(test_db):
    """Create a FastAPI test app with the test database"""
    app = FastAPI()
    app.include_router(router)
    
    # Override the dependency to use our test database
    async def override_get_db():
        db = test_db.SessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    # Override the dependency in the app
    app.dependency_overrides[Database.get_db] = override_get_db
    
    client = TestClient(app)
    return client

@pytest.fixture
def mock_cube_client():
    """Create a mock CubeClient that will return canned responses"""
    with patch("cube_dca.external.cube.cube_client.CubeClient") as mock_client:
        # Configure mocked methods here
        instance = mock_client.return_value
        
        # Mock get_latest_orders to return empty list initially
        instance.get_latest_orders.return_value = []
        
        # Mock place_order to "succeed"
        instance.place_order.return_value = {"orderId": 12345}
        
        yield instance

# Helper function to create a test trade in the database
def create_test_trade(db_session, strategy="twap"):
    """Create a test trade in the database and return its ID"""
    trade = UserTrade(
        id=str(uuid.uuid4()),
        symbol=TEST_SYMBOL,
        side=TEST_SIDE,
        total_quantity=TEST_QUANTITY,
        limit_price=TEST_PRICE,
        strategy=strategy,
        strategy_params={"duration": 60, "interval": 5},
        status=UserTradeStatus.ACTIVE,
        timestamp=datetime.utcnow()
    )
    db_session.add(trade)
    db_session.commit()
    db_session.refresh(trade)
    return trade

# Helper function to create a test order
def create_test_order(db_session, trade_id, status=OrderStatus.FILLED, quantity_pct=0.25):
    """Create a test order for a trade"""
    order = Order(
        id=str(uuid.uuid4()),
        user_trade_id=trade_id,
        symbol=TEST_SYMBOL,
        side="Bid",
        price=TEST_PRICE * 0.99,
        quantity=TEST_QUANTITY * quantity_pct,
        status=status,
        market_id=100001,
        created_at=int(datetime.now().timestamp() * 1_000_000_000),
        filled_at=int(datetime.now().timestamp() * 1_000_000_000) if status == OrderStatus.FILLED else None,
        client_order_id=12345,
        base_amount=str(TEST_QUANTITY * quantity_pct) if status == OrderStatus.FILLED else None,
        quote_amount=str(TEST_PRICE * 0.99 * TEST_QUANTITY * quantity_pct) if status == OrderStatus.FILLED else None,
        fee_amount="0.05" if status == OrderStatus.FILLED else None,
        timestamp=datetime.utcnow()
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)
    return order

# Test list all trades endpoint
def test_list_all_trades(test_app, test_db, mock_cube_client):
    client = test_app
    db_session = test_db.SessionLocal()
    
    # Create a couple of trades
    trade1 = create_test_trade(db_session, "twap")
    trade2 = create_test_trade(db_session, "vwap")
    
    # Create some orders for the first trade
    create_test_order(db_session, trade1.id, OrderStatus.FILLED, 0.25)
    create_test_order(db_session, trade1.id, OrderStatus.OPEN, 0.25)
    
    response = client.get("/trades/")
    
    assert response.status_code == 200
    assert len(response.json()) == 2
    
    # Check that both trades are in the response
    trade_ids = [trade["trade_id"] for trade in response.json()]
    assert trade1.id in trade_ids
    assert trade2.id in trade_ids
    
    # For the first trade, verify it shows 25% progress
    first_trade = next(t for t in response.json() if t["trade_id"] == trade1.id)
    assert first_trade["progress"] == 25.0
    assert first_trade["orders_count"] == 2
    assert first_trade["filled_orders_count"] == 1
    
    db_session.close()

# Test get trade details endpoint
def test_get_trade_details(test_app, test_db, mock_cube_client):
    client = test_app
    db_session = test_db.SessionLocal()
    
    # Create a trade
    trade = create_test_trade(db_session)
    
    # Create an order for the trade
    order = create_test_order(db_session, trade.id)
    
    response = client.get(f"/trades/{trade.id}")
    
    assert response.status_code == 200
    assert response.json()["trade_id"] == trade.id
    assert response.json()["orders_count"] == 1
    assert response.json()["orders"][0]["order_id"] == order.id
    
    db_session.close()

# Test trade not found
def test_get_trade_details_not_found(test_app, test_db, mock_cube_client):
    client = test_app
    
    response = client.get(f"/trades/nonexistent-id")
    
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]

# Test get trade statistics endpoint
def test_get_trade_statistics(test_app, test_db, mock_cube_client):
    client = test_app
    db_session = test_db.SessionLocal()
    
    # Create a trade
    trade = create_test_trade(db_session)
    
    # Create orders for the trade - one filled, one open
    create_test_order(db_session, trade.id, OrderStatus.FILLED, 0.25)
    create_test_order(db_session, trade.id, OrderStatus.OPEN, 0.25)
    
    response = client.get(f"/trades/{trade.id}/stats")
    
    assert response.status_code == 200
    assert response.json()["trade_id"] == trade.id
    assert response.json()["execution_progress"] == 25.0
    assert response.json()["orders_statistics"]["total"] == 2
    assert response.json()["orders_statistics"]["filled"] == 1
    assert response.json()["orders_statistics"]["open"] == 1
    
    db_session.close()

# Test create new trade endpoint
def test_create_new_trade(test_app, test_db, mock_cube_client):
    client = test_app
    
    trade_data = {
        "symbol": TEST_SYMBOL,
        "side": TEST_SIDE,
        "total_quantity": TEST_QUANTITY,
        "limit_price": TEST_PRICE,
        "strategy": "twap",
        "strategy_params": {"duration": 60, "interval": 5}
    }
    
    response = client.post("/trades/", json=trade_data)
    
    assert response.status_code == 201
    assert "trade_id" in response.json()
    assert response.json()["message"] == "Trade created successfully"
    
    # Verify the trade was actually created in the database
    db_session = test_db.SessionLocal()
    trade_id = response.json()["trade_id"]
    trade = db_session.query(UserTrade).filter(UserTrade.id == trade_id).first()
    assert trade is not None
    assert trade.symbol == TEST_SYMBOL
    assert trade.status == UserTradeStatus.ACTIVE
    
    db_session.close()

# Test pause trade endpoint
def test_pause_trade(test_app, test_db, mock_cube_client):
    client = test_app
    db_session = test_db.SessionLocal()
    
    # Create a trade
    trade = create_test_trade(db_session)
    
    response = client.post(f"/trades/{trade.id}/pause")
    
    assert response.status_code == 200
    assert response.json()["trade_id"] == trade.id
    assert response.json()["status"] == "paused"
    assert response.json()["message"] == "Trade paused successfully"
    
    # Verify the trade status was actually updated in the database
    db_session.refresh(trade)
    assert trade.status == UserTradeStatus.PAUSED
    
    db_session.close()

# Test resume trade endpoint
def test_resume_trade(test_app, test_db, mock_cube_client):
    client = test_app
    db_session = test_db.SessionLocal()
    
    # Create a trade and set it to paused
    trade = create_test_trade(db_session)
    trade.status = UserTradeStatus.PAUSED
    db_session.commit()
    
    response = client.post(f"/trades/{trade.id}/resume")
    
    assert response.status_code == 200
    assert response.json()["trade_id"] == trade.id
    assert response.json()["status"] == "active"
    assert response.json()["message"] == "Trade resumed successfully"
    
    # Verify the trade status was actually updated in the database
    db_session.refresh(trade)
    assert trade.status == UserTradeStatus.ACTIVE
    
    db_session.close()

# Test cancel trade endpoint
def test_cancel_trade(test_app, test_db, mock_cube_client):
    client = test_app
    db_session = test_db.SessionLocal()
    
    # Create a trade
    trade = create_test_trade(db_session)
    
    response = client.post(f"/trades/{trade.id}/cancel")
    
    assert response.status_code == 200
    assert response.json()["trade_id"] == trade.id
    assert response.json()["status"] == "stopped"
    assert response.json()["message"] == "Trade canceled successfully"
    
    # Verify the trade status was actually updated in the database
    db_session.refresh(trade)
    assert trade.status == UserTradeStatus.STOPPED
    
    db_session.close()