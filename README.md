# TCG Inventory Manager - TypeScript Edition

A modern TypeScript/Node.js web application for managing Trading Card Game (TCG) collections. This application allows you to track your cards, monitor prices, and manage your inventory with real-time price updates from Scryfall.

## Features

- **Card Management**: Add, edit, delete, and organize your TCG cards
- **Price Tracking**: Real-time price updates from Scryfall API
- **CSV Import**: Import collections from CSV files (Manabox exports supported)
- **Search & Filter**: Advanced filtering by name, rarity, color, mana cost, etc.
- **User Authentication**: Secure user accounts with bcrypt password hashing
- **Responsive Design**: Bootstrap-based UI that works on desktop and mobile
- **Progress Tracking**: Background processing with real-time progress updates

## Technology Stack

- **Backend**: Node.js, Express.js, TypeScript
- **Database**: SQLite3
- **Frontend**: EJS templates, Bootstrap 5, jQuery
- **APIs**: Scryfall API for card data and pricing
- **Authentication**: Express-session with bcrypt

## Quick Start

### Prerequisites

- Node.js 18+ 
- npm or yarn

### Installation

1. Clone the repository
```bash
git clone <repository-url>
cd tcg-inventory-ts
```

2. Install dependencies
```bash
npm install
```

3. Create environment file
```bash
cp .env.example .env
```

4. Build the TypeScript code
```bash
npm run build
```

5. Start the application
```bash
npm start
```

Or for development:
```bash
npm run dev
```

The application will be available at `http://localhost:5001`

### Default Admin Account

- Email: `admin@packrat.local`
- Password: `packrat123`

## Development Commands

```bash
# Development server with hot reload
npm run dev

# Build TypeScript to JavaScript
npm run build

# Start production server
npm start

# Type checking
npm run typecheck

# Linting
npm run lint
```

## Project Structure

```
src/
├── database/           # Database layer
│   └── database.ts     # SQLite database operations
├── middleware/         # Express middleware
│   └── auth.ts         # Authentication middleware
├── routes/             # Express routes
│   ├── auth.ts         # Authentication routes
│   ├── cards.ts        # Card management routes
│   └── api.ts          # API endpoints
├── services/           # Business logic services
│   ├── auth.ts         # Authentication service
│   ├── scryfall.ts     # Scryfall API integration
│   └── csvImport.ts    # CSV processing service
├── types/              # TypeScript type definitions
│   └── index.ts        # Application types
└── index.ts            # Application entry point

views/                  # EJS templates
├── login.ejs
├── register.ejs
├── index.ejs           # Dashboard
├── add_card.ejs
├── card_detail.ejs
├── collections.ejs
└── alerts.ejs
```

## API Endpoints

### Authentication
- `GET /login` - Login page
- `POST /login` - Login user
- `GET /register` - Registration page  
- `POST /register` - Register new user
- `GET /logout` - Logout user

### Card Management
- `GET /` - Dashboard with card listing
- `GET /add_card` - Add card form
- `POST /add_card` - Create new card
- `GET /card_detail/:id` - Card details page
- `POST /edit_card/:id` - Update card
- `POST /delete_card/:id` - Delete card
- `POST /import_csv` - Import cards from CSV

### API Routes
- `GET /api/search_cards?q=query` - Search cards via Scryfall
- `GET /api/cards` - Get user's cards (JSON)
- `GET /api/card/:id/image` - Get card image URL
- `POST /api/delete_all_cards` - Delete all user's cards
- `POST /api/mass_delete` - Delete selected cards
- `POST /api/mass_update_prices` - Update prices for selected cards

## Features in Detail

### CSV Import
The application supports importing cards from CSV files, with automatic mapping of common column names:
- Card Name, Set Name, Set Code
- Collector Number, Quantity, Condition
- Purchase Price, Rarity, Colors
- Mana Cost, Mana Value, Card Type

### Price Updates  
Real-time price fetching from Scryfall API with:
- Rate limiting (100ms delay between requests)
- Support for both regular and foil prices
- Background processing with progress tracking
- Error handling and retry logic

### Search & Filtering
Advanced filtering options:
- Text search across card names, sets, and types
- Filter by rarity, colors, mana value range
- Sorting by name, price, value, quantity
- Pagination for large collections

### Authentication & Security
- Bcrypt password hashing
- Session-based authentication
- CSRF protection
- SQL injection prevention with parameterized queries

## Database Schema

The application uses SQLite with the following main tables:

- `users` - User accounts
- `cards` - Individual cards in collections
- `price_alerts` - Price change notifications
- `collection_templates` - Reusable collection templates
- `card_templates` - Template card definitions

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## Migrating from Python Version

This TypeScript version maintains API compatibility with the original Python/Flask version. You can migrate your existing SQLite database by:

1. Copying your existing `inventory.db` file to the TypeScript project
2. The database schema is compatible between versions
3. User accounts and card data will be preserved

## License

MIT License - see LICENSE file for details

## Support

- Create an issue for bugs or feature requests
- Check the documentation for common questions
- Review the code comments for implementation details