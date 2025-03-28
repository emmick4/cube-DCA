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

# Test data
TEST_SYMBOL = "BTCUSDC"
TEST_QUANTITY = 1.0
TEST_PRICE = 50000.0

@pytest.fixture
def mock_trade():
    """Mock trade for testing"""
    mock_trade = Mock(spec=UserTrade)
    mock_trade.id = str(uuid.uuid4())
    mock_trade.symbol = TEST_SYMBOL
    mock_trade.side = "buy"
    mock_trade.total_quantity = TEST_QUANTITY
    mock_trade.limit_price = TEST_PRICE
    mock_trade.strategy = "twap"
    mock_trade.status = UserTradeStatus.PENDING
    return mock_trade

@pytest.fixture
def mock_db_session():
    """Create a mock database session"""
    mock_session = Mock()
    return mock_session

@patch("src.api.trade_api.Database.get_db")
def test_trade_workflow(mock_get_db, mock_db_session, mock_trade):
    """Test the complete trade lifecycle workflow"""
    mock_get_db.return_value = mock_db_session
    
    # 1. Create a new trade
    with patch("src.api.trade_api.create_trade") as mock_create_trade:
        mock_create_trade.return_value = mock_trade
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
    
    # 2. Get trade details
    with patch("src.api.trade_api.get_trade_info") as mock_get_trade_info:
        mock_get_trade_info.return_value = {
            "trade_id": trade_id,
            "symbol": TEST_SYMBOL,
            "side": "buy",
            "total_quantity": TEST_QUANTITY,
            "limit_price": TEST_PRICE,
            "strategy": "twap",
            "status": "active",  # Now active
            "created_at": datetime.utcnow(),
            "orders_count": 0,
            "orders": []
        }
        response = client.get(f"/trades/{trade_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "active"
    
    # 3. Now the trade is running, get stats
    with patch("src.api.trade_api.get_execution_stats") as mock_get_stats:
        mock_get_stats.return_value = {
            "trade_id": trade_id,
            "symbol": TEST_SYMBOL,
            "side": "buy",
            "strategy": "twap",
            "status": "active",
            "total_target_quantity": TEST_QUANTITY,
            "total_executed_quantity": TEST_QUANTITY * 0.25,  # 25% executed
            "execution_progress": 25.0,
            "average_execution_price": TEST_PRICE * 0.99,  # Good price
            "limit_price": TEST_PRICE,
            "price_improvement_percent": 1.0,
            "total_execution_value": TEST_PRICE * 0.99 * TEST_QUANTITY * 0.25,
            "total_fees": 0.05,
            "execution_time_seconds": 15,
            "orders_statistics": {
                "total": 2,
                "filled": 1,
                "open": 1,
                "canceled": 0,
                "rejected": 0,
                "fill_rate": 50.0
            }
        }
        response = client.get(f"/trades/{trade_id}/stats")
        assert response.status_code == 200
        assert response.json()["execution_progress"] == 25.0
    
    # 4. Pause the trade
    with patch("src.api.trade_api.pause_trade") as mock_pause_trade:
        mock_trade.status = UserTradeStatus.PAUSED
        mock_pause_trade.return_value = mock_trade
        response = client.post(f"/trades/{trade_id}/pause")
        assert response.status_code == 200
        assert response.json()["status"] == "paused"
    
    # 5. Resume the trade
    with patch("src.api.trade_api.resume_trade") as mock_resume_trade:
        mock_trade.status = UserTradeStatus.ACTIVE
        mock_resume_trade.return_value = mock_trade
        response = client.post(f"/trades/{trade_id}/resume")
        assert response.status_code == 200
        assert response.json()["status"] == "active"
    
    # 6. Cancel the trade
    with patch("src.api.trade_api.cancel_trade") as mock_cancel_trade:
        mock_trade.status = UserTradeStatus.STOPPED
        mock_cancel_trade.return_value = mock_trade
        response = client.post(f"/trades/{trade_id}/cancel")
        assert response.status_code == 200
        assert response.json()["status"] == "stopped"
    
    # 7. Get final stats after cancellation
    with patch("src.api.trade_api.get_execution_stats") as mock_get_stats:
        mock_get_stats.return_value = {
            "trade_id": trade_id,
            "symbol": TEST_SYMBOL,
            "side": "buy",
            "strategy": "twap",
            "status": "stopped",
            "total_target_quantity": TEST_QUANTITY,
            "total_executed_quantity": TEST_QUANTITY * 0.5,  # 50% executed before cancel
            "execution_progress": 50.0,
            "average_execution_price": TEST_PRICE * 0.985,
            "limit_price": TEST_PRICE,
            "price_improvement_percent": 1.5,
            "total_execution_value": TEST_PRICE * 0.985 * TEST_QUANTITY * 0.5,
            "total_fees": 0.1,
            "execution_time_seconds": 30,
            "orders_statistics": {
                "total": 4,
                "filled": 2,
                "open": 0,
                "canceled": 2,
                "rejected": 0,
                "fill_rate": 50.0
            }
        }
        response = client.get(f"/trades/{trade_id}/stats")
        assert response.status_code == 200
        assert response.json()["status"] == "stopped"
        assert response.json()["execution_progress"] == 50.0