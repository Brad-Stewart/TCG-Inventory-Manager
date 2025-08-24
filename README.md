# TCG Inventory Manager

A Flask-based web application for managing Trading Card Game (TCG) collections with features for price tracking, bulk operations, and detailed inventory management.

## Features

### Core Functionality
- **Card Management**: Add, edit, and delete cards from your collection
- **CSV Import**: Import cards from Manabox CSV exports
- **Price Tracking**: Automatic price updates via Scryfall API
- **Search & Filtering**: Advanced filtering by name, set, rarity, color, type, and mana value
- **Sorting**: Sort by price, name, rarity, mana value, set, and total value

### Advanced Features
- **Mass Operations**: Bulk price updates and deletions with checkbox selection
- **Card Previews**: Small thumbnail images with hover enlargement
- **Pagination**: Performance-optimized with 50 cards per page
- **Price Alerts**: Track significant price changes
- **User Authentication**: Secure login system with individual collections
- **Responsive Design**: Bootstrap-based UI that works on all devices

### Performance Optimizations
- **Background Processing**: Long-running price updates run in background
- **Rate Limiting**: Respects Scryfall API limits
- **Database Pagination**: Efficient loading of large collections
- **Optimized Queries**: Fast search and filtering

## Installation

### Requirements
- Python 3.7+
- Flask
- SQLite3
- Requests library

### Setup
1. Clone the repository:
```bash
git clone <repository-url>
cd Inventory_System
```

2. Install dependencies:
```bash
pip install flask requests
```

3. Run the application:
```bash
python app.py
```

4. Open your browser to `http://localhost:5000`

## Usage

### Initial Setup
1. Register a new account or use the default admin account
2. Import your collection via CSV or add cards manually
3. Run initial price updates to populate card data

### CSV Import
- Export your collection from Manabox as CSV
- Use the "Import CSV" button on the main page
- The system will automatically map common columns
- Price updates run automatically after import

### Price Management
- **Update Metadata**: Updates cards with missing rarity, color, or type data
- **Update All Prices**: Background process to update all card prices
- **Mass Update**: Select specific cards for bulk price updates

### Mass Operations
- Check boxes next to cards to select multiple items
- Use the mass action panel for bulk operations:
  - Update prices for selected cards
  - Delete selected cards
  - Clear selection

### Card Previews
- Small thumbnail images appear next to card names
- Hover over thumbnails or placeholders for enlarged previews
- Images are fetched dynamically from Scryfall API

## API Endpoints

- `GET /api/cards` - Get paginated card list
- `GET /api/card/<id>/image` - Get card image URL
- `POST /mass_update_prices` - Bulk price updates
- `POST /mass_delete` - Bulk deletions
- `POST /delete_all_cards` - Delete entire collection

## Database Schema

### Cards Table
- Card details (name, set, rarity, colors, type, mana cost)
- Price information (current price, purchase price, total value)
- Inventory data (quantity, condition, foil status)
- Metadata (image URLs, Scryfall IDs, market links)

### Users Table
- Authentication (email, hashed password)
- User settings and preferences

### Price Alerts Table
- Price change tracking
- Configurable thresholds

## Development

### Architecture
- **Backend**: Flask with SQLite database
- **Frontend**: Bootstrap 5 with custom JavaScript
- **API Integration**: Scryfall API for card data and pricing
- **Authentication**: Session-based with secure password hashing

### Key Files
- `app.py` - Main Flask application
- `templates/index.html` - Main inventory dashboard
- `static/js/app.js` - Frontend JavaScript functionality
- `static/css/style.css` - Custom styles

### Performance Considerations
- Pagination limits memory usage
- Background threads for long operations
- API rate limiting to prevent blocking
- Efficient database queries with proper indexing

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is licensed under the MIT License.