# cube-DCA

A simple trading bot for executing automated trading strategies on the Cube exchange.

## Overview

The system works as follows:
- The main file sets up the database and Cube client connection
- The main loop monitors and manages trades:
  - When a trade appears in the database, it spins up a corresponding worker
  - When an order status from Cube diverges from the database state, it syncs them

## Strategies

Two strategies are implemented:
- **TWAP**: Time-Weighted Average Price strategy that splits trades over time
- **Liquidity Maker**: Makes directional liquidity for a token pair (in development)

## Setup

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Configure your API keys in `config/config.json`
4. Run with: `python main.py`

## API

The system includes a REST API for managing trades. Use the `/trades` endpoint to create and monitor trades.

