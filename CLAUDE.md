# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python-based Trading Card Game (TCG) inventory management system that synchronizes card collections between Manabox CSV exports and Google Sheets. The system fetches current market prices from Scryfall API and provides value tracking and analytics.

## Architecture

- **Core Class**: `TCGInventoryManager` in `tcg_inventory_manager.py:17` - Main orchestrator for inventory operations
- **Data Flow**: Manabox CSV → DataFrame processing → Price updates via Scryfall API → Google Sheets sync
- **External APIs**: Scryfall API (free, no auth) for card prices and metadata
- **Storage**: Google Sheets as the primary data store with automated formatting and summary dashboards

## Key Components

- **CSV Import**: `import_manabox_csv()` at `tcg_inventory_manager.py:41` - Processes Manabox exports with column mapping
- **Price Fetching**: `fetch_scryfall_prices()` at `tcg_inventory_manager.py:80` - Retrieves current market prices with caching
- **Google Sheets Integration**: `update_google_sheet()` at `tcg_inventory_manager.py:185` - Creates/updates spreadsheets with formatting
- **Summary Analytics**: `create_summary_sheet()` at `tcg_inventory_manager.py:266` - Generates dashboard with collection statistics

## Development Commands

```bash
# Install dependencies
pip3 install -r requirements.txt

# Run the main synchronization
python3 tcg_inventory_manager.py

# Run the web application
python3 app.py

# Access web interface
# http://localhost:5000
```

## Configuration Requirements

- Google Service Account JSON credentials file
- Manabox CSV export file
- Update paths in `main()` function at `tcg_inventory_manager.py:351`

## Web Application Features

- **Flask Web Interface**: `app.py` - Complete web app for manual inventory management
- **SQLite Database**: Local storage with card details, pricing, and alert history
- **Real-time Price Monitoring**: Background thread checks prices hourly
- **Price Alert System**: Configurable percentage thresholds with notification dashboard
- **Manual Editing**: Add, edit, delete cards through web interface
- **CSV Import**: Upload Manabox exports directly through the web interface

## Data Processing Notes

- Price caching implemented with 1-hour TTL to respect Scryfall rate limits
- Automatic foil vs non-foil price selection based on card data
- Conditional formatting in Google Sheets for price change visualization
- Summary dashboard automatically created with top 10 most valuable cards
- Price alerts triggered only once per 24-hour period per card