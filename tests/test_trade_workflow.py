import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
from datetime import datetime
import uuid
import os
import tempfile
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import logging

from cube_dca.api.trade_api import router
from cube_dca.db.models import UserTrade, Order, UserTradeStatus, OrderStatus, Base
from cube_dca.db.db import Database
from fastapi import FastAPI
from cube_dca.external.cube.types import Market

# Enable debug logging to find the issue
logging.basicConfig(level=logging.DEBUG)

# Test data
TEST_SYMBOL = "BTCUSDC"
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

def test_trade_workflow(test_app, test_db, mock_cube_client):
    """Test the complete trade lifecycle workflow using a real database and mocked API calls"""
    client = test_app
    
    # Print the enum values to debug
    print("OrderStatus values:", [status.value for status in OrderStatus])
    print("CANCELLED enum value:", OrderStatus.CANCELLED.value)
    
    # 1. Create a new trade
    trade_data = {
        "symbol": TEST_SYMBOL,
        "side": "buy",
        "total_quantity": TEST_QUANTITY,
        "limit_price": TEST_PRICE,
        "strategy": "twap",
        "strategy_params": {"duration": 60, "interval": 5}
    }
    response = client.post("/trades/", json=trade_data)
    assert response.status_code == 201
    trade_id = response.json()["trade_id"]
    
    # Verify the trade was actually created in the database
    db_session = test_db.SessionLocal()
    db_trade = db_session.query(UserTrade).filter(UserTrade.id == trade_id).first()
    assert db_trade is not None
    assert db_trade.symbol == TEST_SYMBOL
    assert db_trade.status == UserTradeStatus.ACTIVE
    db_session.close()
    
    # 2. Get trade details
    response = client.get(f"/trades/{trade_id}")
    assert response.status_code == 200
    assert response.json()["symbol"] == TEST_SYMBOL
    assert response.json()["status"] == "active"
    
    # 3. Now simulate some filled orders for the trade
    # We'll create orders directly in the database
    db_session = test_db.SessionLocal()
    order1 = Order(
        id=str(uuid.uuid4()),
        user_trade_id=trade_id,
        symbol=TEST_SYMBOL,
        side="Bid",
        price=TEST_PRICE * 0.99,
        quantity=TEST_QUANTITY * 0.25,
        status=OrderStatus.FILLED,
        market_id=100001,
        created_at=int(datetime.now().timestamp() * 1_000_000_000),
        filled_at=int(datetime.now().timestamp() * 1_000_000_000),
        client_order_id=12345,
        base_amount=str(TEST_QUANTITY * 0.25),
        quote_amount=str(TEST_PRICE * 0.99 * TEST_QUANTITY * 0.25),
        fee_amount="0.05",
        timestamp=datetime.utcnow()
    )
    db_session.add(order1)
    db_session.commit()
    
    # 4. Get execution stats, should show 25% progress
    response = client.get(f"/trades/{trade_id}/stats")
    assert response.status_code == 200
    assert response.json()["execution_progress"] == 25.0
    
    # 5. Pause the trade
    response = client.post(f"/trades/{trade_id}/pause")
    assert response.status_code == 200
    assert response.json()["status"] == "paused"
    
    # Verify trade status in the database
    db_session = test_db.SessionLocal()
    db_trade = db_session.query(UserTrade).filter(UserTrade.id == trade_id).first()
    assert db_trade.status == UserTradeStatus.PAUSED
    db_session.close()
    
    # 6. Resume the trade
    response = client.post(f"/trades/{trade_id}/resume")
    assert response.status_code == 200
    assert response.json()["status"] == "active"
    
    # Verify trade status in the database
    db_session = test_db.SessionLocal()
    db_trade = db_session.query(UserTrade).filter(UserTrade.id == trade_id).first()
    assert db_trade.status == UserTradeStatus.ACTIVE
    db_session.close()
    
    # 7. Add another filled order
    db_session = test_db.SessionLocal()
    order2 = Order(
        id=str(uuid.uuid4()),
        user_trade_id=trade_id,
        symbol=TEST_SYMBOL,
        side="Bid",
        price=TEST_PRICE * 0.98,
        quantity=TEST_QUANTITY * 0.25,
        status=OrderStatus.FILLED,
        market_id=100001,
        created_at=int(datetime.now().timestamp() * 1_000_000_000),
        filled_at=int(datetime.now().timestamp() * 1_000_000_000),
        client_order_id=12346,
        base_amount=str(TEST_QUANTITY * 0.25),
        quote_amount=str(TEST_PRICE * 0.98 * TEST_QUANTITY * 0.25),
        fee_amount="0.05",
        timestamp=datetime.utcnow()
    )
    db_session.add(order2)
    db_session.commit()
    
    # 8. Cancel the trade
    response = client.post(f"/trades/{trade_id}/cancel")
    assert response.status_code == 200
    assert response.json()["status"] == "stopped"
    
    # Verify trade status in the database
    db_session = test_db.SessionLocal()
    db_trade = db_session.query(UserTrade).filter(UserTrade.id == trade_id).first()
    assert db_trade.status == UserTradeStatus.STOPPED
    db_session.close()
    
    # 9. Get final stats after cancellation - should show 50% progress
    response = client.get(f"/trades/{trade_id}/stats")
    assert response.status_code == 200
    assert response.json()["status"] == "stopped"
    assert response.json()["execution_progress"] == 50.0