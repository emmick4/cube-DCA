import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
from datetime import datetime
import uuid

from api.trade_api import router
from db.models import UserTrade, Order, UserTradeStatus, OrderStatus
from fastapi import FastAPI
from db.db import Database

# Setup test app
app = FastAPI()
app.include_router(router)

client = TestClient(app)

# Mock data
MOCK_TRADE_ID = "test-trade-id"
MOCK_NEW_TRADE_ID = "new-test-trade-id"
MOCK_SYMBOL = "BTCUSDC"
MOCK_SIDE = "buy"
MOCK_QUANTITY = 1.0
MOCK_PRICE = 50000.0
MOCK_TIMESTAMP = datetime.utcnow()

@pytest.fixture
def mock_db_session():
    """Create a mock database session"""
    mock_session = Mock()
    return mock_session

@pytest.fixture
def mock_trade():
    """Create a mock UserTrade"""
    mock_trade = Mock(spec=UserTrade)
    mock_trade.id = MOCK_TRADE_ID
    mock_trade.symbol = MOCK_SYMBOL
    mock_trade.side = MOCK_SIDE
    mock_trade.total_quantity = MOCK_QUANTITY
    mock_trade.limit_price = MOCK_PRICE
    mock_trade.strategy = "twap"
    mock_trade.strategy_params = {"duration": 60, "interval": 5}
    mock_trade.timestamp = MOCK_TIMESTAMP
    mock_trade.status = UserTradeStatus.ACTIVE
    return mock_trade

@pytest.fixture
def mock_order():
    """Create a mock Order"""
    mock_order = Mock(spec=Order)
    mock_order.id = "test-order-id"
    mock_order.user_trade_id = MOCK_TRADE_ID
    mock_order.symbol = MOCK_SYMBOL
    mock_order.side = MOCK_SIDE
    mock_order.price = MOCK_PRICE
    mock_order.quantity = MOCK_QUANTITY / 4  # Split the order
    mock_order.status = OrderStatus.FILLED
    mock_order.timestamp = MOCK_TIMESTAMP
    mock_order.created_at = int(MOCK_TIMESTAMP.timestamp() * 1_000_000_000)
    mock_order.filled_at = int(MOCK_TIMESTAMP.timestamp() * 1_000_000_000) + 10_000_000_000
    mock_order.base_amount = str(MOCK_QUANTITY / 4)
    mock_order.quote_amount = str(MOCK_PRICE * MOCK_QUANTITY / 4)
    mock_order.fee_amount = "0.1"
    return mock_order

# Test list all trades endpoint
@patch("api.trade_api.get_all_trades_summary")
@patch("api.trade_api.Database.get_db")
def test_list_all_trades(mock_get_db, mock_get_all_trades, mock_db_session):
    mock_get_db.return_value = mock_db_session
    mock_get_all_trades.return_value = [
        {
            "trade_id": MOCK_TRADE_ID,
            "symbol": MOCK_SYMBOL,
            "side": MOCK_SIDE,
            "strategy": "twap",
            "status": "active",
            "created_at": MOCK_TIMESTAMP,
            "target_quantity": MOCK_QUANTITY,
            "executed_quantity": MOCK_QUANTITY / 2,
            "progress": 50.0,
            "avg_price": MOCK_PRICE,
            "limit_price": MOCK_PRICE,
            "orders_count": 2,
            "filled_orders_count": 1
        }
    ]
    
    response = client.get("/trades/")
    
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["trade_id"] == MOCK_TRADE_ID
    assert response.json()[0]["progress"] == 50.0
    mock_get_all_trades.assert_called_once_with(mock_db_session)

# Test get trade details endpoint
@patch("api.trade_api.get_trade_info")
@patch("api.trade_api.Database.get_db")
def test_get_trade_details(mock_get_db, mock_get_trade_info, mock_db_session, mock_trade, mock_order):
    mock_get_db.return_value = mock_db_session
    mock_get_trade_info.return_value = {
        "trade_id": mock_trade.id,
        "symbol": mock_trade.symbol,
        "side": mock_trade.side,
        "total_quantity": mock_trade.total_quantity,
        "limit_price": mock_trade.limit_price,
        "strategy": mock_trade.strategy,
        "status": mock_trade.status.value,
        "created_at": mock_trade.timestamp,
        "orders_count": 1,
        "orders": [
            {
                "order_id": mock_order.id,
                "symbol": mock_order.symbol,
                "side": mock_order.side,
                "price": mock_order.price,
                "quantity": mock_order.quantity,
                "status": mock_order.status.value,
                "created_at": datetime.fromtimestamp(mock_order.created_at / 1_000_000_000),
                "filled_at": datetime.fromtimestamp(mock_order.filled_at / 1_000_000_000),
                "base_amount": mock_order.base_amount,
                "quote_amount": mock_order.quote_amount,
                "fee_amount": mock_order.fee_amount
            }
        ]
    }
    
    response = client.get(f"/trades/{MOCK_TRADE_ID}")
    
    assert response.status_code == 200
    assert response.json()["trade_id"] == MOCK_TRADE_ID
    assert response.json()["orders_count"] == 1
    mock_get_trade_info.assert_called_once_with(mock_db_session, MOCK_TRADE_ID)

# Test trade not found
@patch("api.trade_api.get_trade_info")
@patch("api.trade_api.Database.get_db")
def test_get_trade_details_not_found(mock_get_db, mock_get_trade_info, mock_db_session):
    mock_get_db.return_value = mock_db_session
    mock_get_trade_info.return_value = None
    
    response = client.get(f"/trades/nonexistent-id")
    
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]

# Test get trade statistics endpoint
@patch("api.trade_api.get_execution_stats")
@patch("api.trade_api.Database.get_db")
def test_get_trade_statistics(mock_get_db, mock_get_execution_stats, mock_db_session, mock_trade):
    mock_get_db.return_value = mock_db_session
    mock_get_execution_stats.return_value = {
        "trade_id": mock_trade.id,
        "symbol": mock_trade.symbol,
        "side": mock_trade.side,
        "strategy": mock_trade.strategy,
        "status": mock_trade.status.value,
        "total_target_quantity": mock_trade.total_quantity,
        "total_executed_quantity": mock_trade.total_quantity / 2,
        "execution_progress": 50.0,
        "average_execution_price": MOCK_PRICE,
        "limit_price": mock_trade.limit_price,
        "price_improvement_percent": 0.0,
        "total_execution_value": MOCK_PRICE * mock_trade.total_quantity / 2,
        "total_fees": 0.1,
        "execution_time_seconds": 10,
        "orders_statistics": {
            "total": 2,
            "filled": 1,
            "open": 1,
            "canceled": 0,
            "rejected": 0,
            "fill_rate": 50.0
        }
    }
    
    response = client.get(f"/trades/{MOCK_TRADE_ID}/stats")
    
    assert response.status_code == 200
    assert response.json()["trade_id"] == MOCK_TRADE_ID
    assert response.json()["execution_progress"] == 50.0
    mock_get_execution_stats.assert_called_once_with(mock_db_session, MOCK_TRADE_ID)

# Test create new trade endpoint
@patch("api.trade_api.create_trade")
@patch("api.trade_api.Database.get_db")
def test_create_new_trade(mock_get_db, mock_create_trade, mock_db_session, mock_trade):
    mock_get_db.return_value = mock_db_session
    mock_create_trade.return_value = mock_trade
    
    trade_data = {
        "symbol": MOCK_SYMBOL,
        "side": MOCK_SIDE,
        "total_quantity": MOCK_QUANTITY,
        "limit_price": MOCK_PRICE,
        "strategy": "twap",
        "strategy_params": {"duration": 60, "interval": 5}
    }
    
    response = client.post("/trades/", json=trade_data)
    
    assert response.status_code == 201
    assert response.json()["trade_id"] == MOCK_TRADE_ID
    assert response.json()["message"] == "Trade created successfully"
    mock_create_trade.assert_called_once()

# Test pause trade endpoint
@patch("api.trade_api.pause_trade")
@patch("api.trade_api.Database.get_db")
def test_pause_trade(mock_get_db, mock_pause_trade, mock_db_session, mock_trade):
    mock_get_db.return_value = mock_db_session
    mock_trade.status = UserTradeStatus.PAUSED
    mock_pause_trade.return_value = mock_trade
    
    response = client.post(f"/trades/{MOCK_TRADE_ID}/pause")
    
    assert response.status_code == 200
    assert response.json()["trade_id"] == MOCK_TRADE_ID
    assert response.json()["status"] == "paused"
    assert response.json()["message"] == "Trade paused successfully"
    mock_pause_trade.assert_called_once_with(mock_db_session, MOCK_TRADE_ID)

# Test resume trade endpoint
@patch("api.trade_api.resume_trade")
@patch("api.trade_api.Database.get_db")
def test_resume_trade(mock_get_db, mock_resume_trade, mock_db_session, mock_trade):
    mock_get_db.return_value = mock_db_session
    mock_trade.status = UserTradeStatus.ACTIVE
    mock_resume_trade.return_value = mock_trade
    
    response = client.post(f"/trades/{MOCK_TRADE_ID}/resume")
    
    assert response.status_code == 200
    assert response.json()["trade_id"] == MOCK_TRADE_ID
    assert response.json()["status"] == "active"
    assert response.json()["message"] == "Trade resumed successfully"
    mock_resume_trade.assert_called_once_with(mock_db_session, MOCK_TRADE_ID)

# Test cancel trade endpoint
@patch("api.trade_api.cancel_trade")
@patch("api.trade_api.Database.get_db")
def test_cancel_trade(mock_get_db, mock_cancel_trade, mock_db_session, mock_trade):
    mock_get_db.return_value = mock_db_session
    mock_trade.status = UserTradeStatus.STOPPED
    mock_cancel_trade.return_value = mock_trade
    
    response = client.post(f"/trades/{MOCK_TRADE_ID}/cancel")
    
    assert response.status_code == 200
    assert response.json()["trade_id"] == MOCK_TRADE_ID
    assert response.json()["status"] == "stopped"
    assert response.json()["message"] == "Trade canceled successfully"
    mock_cancel_trade.assert_called_once_with(mock_db_session, MOCK_TRADE_ID)