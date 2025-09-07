# TCG Inventory Manager

A comprehensive web application for managing Trading Card Game (TCG) collections with features for price tracking, bulk operations, and detailed inventory management.

## 🚀 **Version 2.0 - TypeScript Edition Available!**

This repository now contains **both versions**:
- 📁 **Python/Flask** (original) - Stable, feature-complete
- 📁 **TypeScript/Express.js** (new) - Modern, type-safe rewrite

---

## 🆕 **TypeScript Version (Recommended)**

A modern TypeScript/Node.js rewrite with full feature parity, enhanced type safety, and improved developer experience.

### **Quick Start (TypeScript)**

```bash
# Navigate to TypeScript version
cd tcg-inventory-ts/

# Install dependencies
npm install

# Build the application
npm run build

# Start the server
npm start

# Or run in development mode
npm run dev
```

**Access:** http://localhost:5001  
**Login:** `admin@packrat.local` / `packrat123`

### **TypeScript Features**

- ✅ **Type Safety** - Full TypeScript with strict typing
- ✅ **Modern Stack** - Express.js, EJS templates, SQLite
- ✅ **Hot Reload** - Development server with automatic restarts
- ✅ **Better Performance** - Optimized async/await database operations
- ✅ **Enhanced Security** - Bcrypt password hashing, session management
- ✅ **Developer Experience** - ESLint, proper error handling, modular architecture

---

## 📊 **Core Features (Both Versions)**

### **Card Management**
- Add, edit, and delete cards from your collection
- Card detail pages with images and market data
- Bulk operations (delete, price updates) with checkbox selection
- Advanced search and filtering capabilities

### **Price Tracking**
- Automatic price updates via Scryfall API with rate limiting
- Real-time background processing with progress indicators
- Price change tracking and alerts
- Foil vs non-foil price support

### **Import & Export**
- CSV import from Manabox exports with automatic column mapping
- Background processing for large imports
- Template support for reusable collections

### **Advanced Features**
- User authentication with secure password hashing
- Responsive Bootstrap UI that works on all devices
- Card image previews with hover enlargement
- Pagination for performance with large collections
- Search by name, set, rarity, color, type, and mana value

---

## 🐍 **Python Version (Original)**

The original Flask-based implementation with Google Sheets integration.

### **Quick Start (Python)**

```bash
# Install dependencies
pip install flask requests pandas

# Run the application
python app.py
```

**Access:** http://localhost:5000

### **Python-Specific Features**
- Google Sheets integration for cloud storage
- Pandas DataFrame processing
- Collection synchronization capabilities

---

## 🔧 **Development**

### **Architecture Comparison**

| Feature | Python Version | TypeScript Version |
|---------|----------------|-------------------|
| **Web Framework** | Flask | Express.js |
| **Database** | SQLite | SQLite |
| **Templates** | Jinja2 | EJS |
| **Type Safety** | ❌ | ✅ Full TypeScript |
| **Development** | Basic reload | Hot reload + linting |
| **Authentication** | SHA256 | Bcrypt |
| **API Integration** | Requests | Axios |
| **Package Management** | pip | npm |

### **Shared Database Schema**

Both versions use compatible SQLite databases:

- **cards** - Card details, pricing, and inventory data
- **users** - Authentication and user preferences
- **price_alerts** - Price change notifications
- **collection_templates** - Reusable collection definitions

### **API Endpoints**

Both versions expose similar REST APIs:

- `GET /api/cards` - Get user's card collection
- `GET /api/search_cards` - Search Scryfall for cards
- `POST /api/mass_delete` - Bulk delete operations
- `POST /api/mass_update_prices` - Bulk price updates
- `POST /import_csv` - CSV import functionality

---

## 📱 **Usage**

### **Initial Setup**
1. Register a new account or use default admin credentials
2. Import your collection via CSV or add cards manually
3. Run price updates to populate current market values

### **CSV Import**
- Export your collection from Manabox as CSV
- Use the "Import CSV" button on the dashboard
- System automatically maps common column names
- Background processing shows real-time progress

### **Mass Operations**
- Select multiple cards using checkboxes
- Bulk update prices for selected cards
- Mass delete unwanted cards
- Progress tracking for long-running operations

---

## 🌐 **API Integration**

### **Scryfall API**
- Comprehensive Magic: The Gathering card database
- Real-time pricing data (USD, USD Foil)
- High-resolution card images
- Card metadata (rarity, colors, mana cost, type)
- Rate limiting compliance (100ms delays)

---

## 🚀 **Deployment**

### **TypeScript Version**
```bash
# Production build
npm run build
npm start

# Using PM2
pm2 start dist/index.js --name tcg-inventory

# Docker (if Dockerfile exists)
docker build -t tcg-inventory .
docker run -p 5001:5001 tcg-inventory
```

### **Python Version**
```bash
# Using Gunicorn
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app

# Environment variables
export FLASK_ENV=production
export DATABASE_PATH=/path/to/inventory.db
```

---

## 🤝 **Contributing**

1. Fork the repository
2. Choose your preferred version (Python or TypeScript)
3. Create a feature branch
4. Make your changes with tests
5. Submit a pull request

### **Development Guidelines**
- Follow existing code style and patterns
- Add type annotations (TypeScript) or docstrings (Python)
- Test your changes thoroughly
- Update documentation as needed

---

## 📄 **License**

MIT License - see LICENSE file for details

---

## 🎯 **Roadmap**

### **Upcoming Features**
- [ ] Mobile app companion
- [ ] Advanced analytics dashboard  
- [ ] Collection sharing and social features
- [ ] Integration with more card databases
- [ ] Automated deck building suggestions
- [ ] Advanced price prediction algorithms

### **Version 3.0 Considerations**
- GraphQL API layer
- Real-time websocket updates
- Advanced caching strategies
- Machine learning price predictions
- Multi-language support

---

## 📞 **Support**

- 🐛 **Bug Reports:** Create an issue with detailed steps to reproduce
- 💡 **Feature Requests:** Open an issue with your suggested enhancement
- 📚 **Documentation:** Check the README and code comments
- 💬 **Questions:** Start a discussion for general questions

---

**Choose your adventure:** Pick the Python version for simplicity or the TypeScript version for modern development practices!