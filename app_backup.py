from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import threading
import time
import queue
import requests
import os
import json
import logging
import hashlib
import secrets
from functools import wraps

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# Simple progress tracking for polling
active_updates = {}
progress_state = {}  # Store latest progress for polling

class InventoryApp:
    def __init__(self):
        self.init_database()
        self.price_alert_thresholds = {}
        
    def init_database(self):
        """Initialize SQLite database for inventory storage"""
        conn = sqlite3.connect('inventory.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_name TEXT NOT NULL,
                set_name TEXT,
                set_code TEXT,
                collector_number TEXT,
                quantity INTEGER DEFAULT 1,
                is_foil BOOLEAN DEFAULT 0,
                condition TEXT DEFAULT 'Near Mint',
                language TEXT DEFAULT 'English',
                purchase_price REAL DEFAULT 0,
                current_price REAL DEFAULT 0,
                price_change REAL DEFAULT 0,
                total_value REAL DEFAULT 0,
                market_url TEXT,
                image_url TEXT,
                rarity TEXT,
                colors TEXT,
                mana_cost TEXT,
                mana_value INTEGER DEFAULT 0,
                card_type TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                price_alert_threshold REAL DEFAULT 0,
                UNIQUE(card_name, set_code, collector_number, is_foil, condition)
            )
        ''')
        
        # Add new columns to existing tables
        try:
            cursor.execute('ALTER TABLE cards ADD COLUMN rarity TEXT')
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        try:
            cursor.execute('ALTER TABLE cards ADD COLUMN colors TEXT')
        except sqlite3.OperationalError:
            pass
            
        try:
            cursor.execute('ALTER TABLE cards ADD COLUMN mana_cost TEXT')
        except sqlite3.OperationalError:
            pass
            
        try:
            cursor.execute('ALTER TABLE cards ADD COLUMN mana_value INTEGER DEFAULT 0')
        except sqlite3.OperationalError:
            pass
            
        try:
            cursor.execute('ALTER TABLE cards ADD COLUMN card_type TEXT')
        except sqlite3.OperationalError:
            pass
        
        try:
            cursor.execute('ALTER TABLE cards ADD COLUMN user_id INTEGER')
        except sqlite3.OperationalError:
            pass
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS price_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_id INTEGER,
                alert_type TEXT,
                threshold_value REAL,
                current_value REAL,
                triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_read BOOLEAN DEFAULT 0,
                FOREIGN KEY (card_id) REFERENCES cards (id)
            )
        ''')
        
        # Users table for authentication
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            )
        ''')
        
        # Collection templates table for shareable collection definitions
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS collection_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                template_hash TEXT UNIQUE NOT NULL,
                created_by INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_public BOOLEAN DEFAULT 0,
                FOREIGN KEY (created_by) REFERENCES users (id)
            )
        ''')
        
        # Card templates for reusable card definitions
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS card_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_id INTEGER NOT NULL,
                card_name TEXT NOT NULL,
                set_name TEXT,
                set_code TEXT,
                collector_number TEXT,
                is_foil BOOLEAN DEFAULT 0,
                condition TEXT DEFAULT 'Near Mint',
                language TEXT DEFAULT 'English',
                quantity INTEGER DEFAULT 1,
                rarity TEXT,
                colors TEXT,
                mana_cost TEXT,
                mana_value INTEGER DEFAULT 0,
                card_type TEXT,
                template_hash TEXT NOT NULL,
                FOREIGN KEY (template_id) REFERENCES collection_templates (id)
            )
        ''')
        
        # User collection instances (independent copies)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_collection_instances (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                template_id INTEGER NOT NULL,
                instance_name TEXT NOT NULL,
                imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (template_id) REFERENCES collection_templates (id),
                UNIQUE(user_id, template_id)
            )
        ''')
        
        # Add template reference to cards for linking to collection templates
        try:
            cursor.execute('ALTER TABLE cards ADD COLUMN template_hash TEXT')
        except sqlite3.OperationalError:
            pass  # Column already exists
            
        try:
            cursor.execute('ALTER TABLE cards ADD COLUMN source_template_id INTEGER')
        except sqlite3.OperationalError:
            pass  # Column already exists
            
        try:
            cursor.execute('ALTER TABLE cards ADD COLUMN image_url_back TEXT')
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        conn.commit()
        conn.close()
        
    def get_db_connection(self):
        """Get database connection with proper configuration"""
        conn = sqlite3.connect('inventory.db', timeout=30.0)
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for better concurrency
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA synchronous=NORMAL') 
        conn.execute('PRAGMA cache_size=1000')
        conn.execute('PRAGMA temp_store=memory')
        return conn

inventory_app = InventoryApp()

# Authentication helper functions
def hash_password(password):
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, password_hash):
    """Verify password against hash"""
    return hashlib.sha256(password.encode()).hexdigest() == password_hash

def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_current_user_id():
    """Get current logged-in user ID"""
    return session.get('user_id')

def create_collection_template(df, template_name, description="", user_id=None, make_public=False):
    """Create a reusable collection template from DataFrame"""
    if user_id is None:
        user_id = get_current_user_id()
    
    # Generate template hash based on content
    content_string = f"{template_name}_{len(df)}"
    for _, row in df.iterrows():
        content_string += f"{row.get('card_name', '')}_{row.get('set_code', '')}_{row.get('collector_number', '')}"
    
    template_hash = hashlib.md5(content_string.encode()).hexdigest()
    
    conn = inventory_app.get_db_connection()
    
    # Check if template already exists
    existing = conn.execute('SELECT id FROM collection_templates WHERE template_hash = ?', (template_hash,)).fetchone()
    if existing:
        conn.close()
        return existing['id']
    
    # Create collection template
    cursor = conn.execute('''
        INSERT INTO collection_templates (name, description, template_hash, created_by, is_public)
        VALUES (?, ?, ?, ?, ?)
    ''', (template_name, description, template_hash, user_id, make_public))
    
    template_id = cursor.lastrowid
    
    # Create card templates
    for _, row in df.iterrows():
        card_name = str(row.get('card_name', '')).strip()
        if not card_name or card_name == 'nan':
            continue
            
        conn.execute('''
            INSERT INTO card_templates 
            (template_id, card_name, set_name, set_code, collector_number, is_foil, 
             condition, language, quantity, rarity, colors, mana_cost, mana_value, card_type, template_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            template_id,
            card_name,
            str(row.get('set_name', '')).strip(),
            str(row.get('set_code', '')).strip(),
            str(row.get('collector_number', '')).strip(),
            bool(row.get('is_foil', False)),
            str(row.get('condition', 'Near Mint')).strip(),
            str(row.get('language', 'English')).strip(),
            int(row.get('quantity', 1)),
            str(row.get('rarity', '')).strip(),
            str(row.get('colors', '')).strip(),
            str(row.get('mana_cost', '')).strip(),
            int(row.get('mana_value', 0)),
            str(row.get('card_type', '')).strip(),
            template_hash
        ))
    
    conn.commit()
    conn.close()
    
    return template_id

def import_template_as_user_collection(template_id, user_id=None, instance_name=None):
    """Import a collection template as independent user cards"""
    if user_id is None:
        user_id = get_current_user_id()
    
    conn = inventory_app.get_db_connection()
    
    # Get template info
    template = conn.execute('SELECT * FROM collection_templates WHERE id = ?', (template_id,)).fetchone()
    if not template:
        conn.close()
        return 0
    
    if instance_name is None:
        instance_name = template['name']
    
    # Check if user already has this template imported
    existing = conn.execute('SELECT id FROM user_collection_instances WHERE user_id = ? AND template_id = ?', 
                           (user_id, template_id)).fetchone()
    
    # Get card templates
    card_templates = conn.execute('SELECT * FROM card_templates WHERE template_id = ?', (template_id,)).fetchall()
    
    imported_count = 0
    imported_card_ids = []
    
    for card_template in card_templates:
        try:
            # Create independent card copy for this user
            cursor = conn.execute('''
                INSERT OR REPLACE INTO cards 
                (card_name, set_name, set_code, collector_number, quantity, is_foil, 
                 condition, language, purchase_price, current_price, price_change, 
                 total_value, rarity, colors, mana_cost, mana_value, card_type, 
                 image_url_back, user_id, template_hash, source_template_id, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                card_template['card_name'],
                card_template['set_name'],
                card_template['set_code'],
                card_template['collector_number'],
                card_template['quantity'],
                card_template['is_foil'],
                card_template['condition'],
                card_template['language'],
                0.0,  # purchase_price - user can set their own
                0.0,  # current_price - will be updated
                0.0,  # price_change
                0.0,  # total_value
                card_template['rarity'],
                card_template['colors'],
                card_template['mana_cost'],
                card_template['mana_value'],
                card_template['card_type'],
                '',   # image_url_back - will be updated
                user_id,
                card_template['template_hash'],
                template_id,
                datetime.now().isoformat()
            ))
            imported_card_ids.append(cursor.lastrowid)
            imported_count += 1
            
        except sqlite3.IntegrityError as e:
            logger.warning(f"Skipping duplicate card {card_template['card_name']}: {e}")
    
    # Record the instance
    if not existing:
        conn.execute('''
            INSERT INTO user_collection_instances (user_id, template_id, instance_name)
            VALUES (?, ?, ?)
        ''', (user_id, template_id, instance_name))
    
    conn.commit()
    conn.close()
    
    # Update prices for imported cards
    if imported_card_ids:
        update_card_prices_and_metadata(imported_card_ids)
    
    return imported_count

def update_card_prices_and_metadata(card_ids):
    """Update prices and metadata for specific card IDs"""
    if not card_ids:
        return 0
    
    conn = inventory_app.get_db_connection()
    updated_count = 0
    
    # Get cards by IDs
    placeholders = ','.join(['?' for _ in card_ids])
    cards = conn.execute(f'SELECT * FROM cards WHERE id IN ({placeholders})', card_ids).fetchall()
    
    for card in cards:
        try:
            logger.info(f"Updating metadata for: {card['card_name']}")
            card_data = fetch_scryfall_data_standalone(card['card_name'], card['set_code'], card['collector_number'] if card['collector_number'] else None)
            current_price = float(card_data.get('usd_foil' if card['is_foil'] else 'usd', 0) or 0)
            total_value = current_price * card['quantity']
            price_change = current_price - (card['purchase_price'] or 0)
            
            # Update card with all data
            conn.execute('''
                UPDATE cards 
                SET current_price = ?, total_value = ?, price_change = ?, 
                    market_url = ?, image_url = ?, image_url_back = ?, rarity = ?, colors = ?, 
                    mana_cost = ?, mana_value = ?, card_type = ?, last_updated = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (current_price, total_value, price_change, 
                  card_data.get('market_url', ''), card_data.get('image_url', ''),
                  card_data.get('image_url_back', ''), card_data.get('rarity', ''), card_data.get('colors', ''),
                  card_data.get('mana_cost', ''), card_data.get('mana_value', 0),
                  card_data.get('card_type', ''), card['id']))
            
            updated_count += 1
            
        except Exception as e:
            logger.error(f"Could not update metadata for {card['card_name']}: {e}")
    
    conn.commit()
    conn.close()
    return updated_count

# Authentication routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    # If user is already logged in, redirect to dashboard
    if 'user_id' in session:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        
        if not email or not password:
            flash('Please enter both email and password', 'error')
            return render_template('login.html')
        
        conn = inventory_app.get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()
        
        if user and verify_password(password, user['password_hash']):
            session['user_id'] = user['id']
            session['user_email'] = user['email']
            
            # Update last login
            conn = inventory_app.get_db_connection()
            conn.execute('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?', (user['id'],))
            conn.commit()
            conn.close()
            
            flash('Logged in successfully!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid email or password', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration"""
    # If user is already logged in, redirect to dashboard
    if 'user_id' in session:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if not email or not password:
            flash('Please enter both email and password', 'error')
            return render_template('register.html')
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('register.html')
        
        if len(password) < 6:
            flash('Password must be at least 6 characters long', 'error')
            return render_template('register.html')
        
        # Check if user already exists
        conn = inventory_app.get_db_connection()
        existing_user = conn.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
        
        if existing_user:
            flash('Email already registered', 'error')
            conn.close()
            return render_template('register.html')
        
        # Create new user
        password_hash = hash_password(password)
        conn.execute('INSERT INTO users (email, password_hash) VALUES (?, ?)', (email, password_hash))
        conn.commit()
        
        # Get the new user ID and log them in
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()
        
        session['user_id'] = user['id']
        session['user_email'] = user['email']
        
        flash('Account created successfully!', 'success')
        return redirect(url_for('index'))
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    """User logout"""
    session.clear()
    flash('Logged out successfully', 'info')
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    """Main inventory dashboard"""
    # Get filter parameters
    rarity_filter = request.args.get('rarity', '')
    color_filter = request.args.get('color', '')
    card_type_filter = request.args.get('card_type', '')
    mana_min = request.args.get('mana_min', '')
    mana_max = request.args.get('mana_max', '')
    name_search = request.args.get('search', '')
    sort_by = request.args.get('sort', 'total_value')
    sort_order = request.args.get('order', 'desc')
    
    # Pagination parameters
    page = int(request.args.get('page', 1))
    per_page = 50  # Show 50 cards per page
    offset = (page - 1) * per_page
    
    conn = inventory_app.get_db_connection()
    current_user_id = get_current_user_id()
    
    # Build query with filters (including user filter)
    query = 'SELECT * FROM cards WHERE user_id = ?'
    params = [current_user_id]
    
    if rarity_filter:
        query += ' AND rarity = ?'
        params.append(rarity_filter)
    
    if color_filter:
        query += ' AND colors = ?'
        params.append(color_filter)
    
    if card_type_filter:
        query += ' AND card_type LIKE ?'
        params.append(f'%{card_type_filter}%')
    
    if mana_min:
        query += ' AND mana_value >= ?'
        params.append(int(mana_min))
    
    if mana_max:
        query += ' AND mana_value <= ?'
        params.append(int(mana_max))
    
    if name_search:
        query += ' AND (card_name LIKE ? OR set_name LIKE ?)'
        search_term = f'%{name_search}%'
        params.extend([search_term, search_term])
    
    # Add sorting
    valid_sorts = ['card_name', 'current_price', 'total_value', 'mana_value', 'rarity', 'card_type', 'set_name']
    if sort_by in valid_sorts:
        query += f' ORDER BY {sort_by}'
        if sort_order == 'desc':
            query += ' DESC'
        else:
            query += ' ASC'
    else:
        query += ' ORDER BY total_value DESC'
    
    # Get total count for pagination
    count_query = query.replace('SELECT *', 'SELECT COUNT(*)', 1)
    total_cards = conn.execute(count_query, params).fetchone()[0]
    
    # Add pagination
    query += f' LIMIT {per_page} OFFSET {offset}'
    
    cards = conn.execute(query, params).fetchall()
    
    # Calculate pagination info
    total_pages = (total_cards + per_page - 1) // per_page
    
    # Get summary statistics for current user
    stats = conn.execute('''
        SELECT 
            COUNT(*) as total_cards,
            SUM(quantity) as total_quantity,
            SUM(total_value) as total_value,
            AVG(current_price) as avg_price
        FROM cards
        WHERE user_id = ?
    ''', (current_user_id,)).fetchone()
    
    # Get filter options for current user
    rarities = conn.execute('SELECT DISTINCT rarity FROM cards WHERE user_id = ? AND rarity IS NOT NULL AND rarity != "" ORDER BY rarity', (current_user_id,)).fetchall()
    colors = conn.execute('SELECT DISTINCT colors FROM cards WHERE user_id = ? AND colors IS NOT NULL AND colors != "" ORDER BY colors', (current_user_id,)).fetchall()
    card_types = conn.execute('SELECT DISTINCT card_type FROM cards WHERE user_id = ? AND card_type IS NOT NULL AND card_type != "" ORDER BY card_type', (current_user_id,)).fetchall()
    
    # Get recent price alerts for current user
    alerts = conn.execute('''
        SELECT pa.*, c.card_name, c.set_name 
        FROM price_alerts pa
        JOIN cards c ON pa.card_id = c.id
        WHERE pa.is_read = 0 AND c.user_id = ?
        ORDER BY pa.triggered_at DESC
        LIMIT 10
    ''', (current_user_id,)).fetchall()
    
    conn.close()
    
    return render_template('index.html', 
                         cards=cards, 
                         stats=stats, 
                         alerts=alerts,
                         rarities=rarities,
                         colors=colors,
                         card_types=card_types,
                         current_filters={
                             'rarity': rarity_filter,
                             'color': color_filter,
                             'card_type': card_type_filter,
                             'mana_min': mana_min,
                             'mana_max': mana_max,
                             'search': name_search,
                             'sort': sort_by,
                             'order': sort_order
                         },
                         pagination={
                             'page': page,
                             'per_page': per_page,
                             'total': total_cards,
                             'pages': total_pages,
                             'has_prev': page > 1,
                             'has_next': page < total_pages,
                             'prev_num': page - 1 if page > 1 else None,
                             'next_num': page + 1 if page < total_pages else None
                         })

@app.route('/card/<int:card_id>')
@login_required
def card_detail(card_id):
    """Card detail and edit page"""
    conn = inventory_app.get_db_connection()
    card = conn.execute('SELECT * FROM cards WHERE id = ?', (card_id,)).fetchone()
    conn.close()
    
    if not card:
        flash('Card not found')
        return redirect(url_for('index'))
    
    return render_template('card_detail.html', card=card)

@app.route('/edit_card/<int:card_id>', methods=['POST'])
def edit_card(card_id):
    """Update card details"""
    conn = inventory_app.get_db_connection()
    
    # Get form data
    quantity = int(request.form.get('quantity', 1))
    condition = request.form.get('condition', 'Near Mint')
    purchase_price = float(request.form.get('purchase_price', 0))
    alert_threshold = float(request.form.get('alert_threshold', 0))
    
    # Update card
    conn.execute('''
        UPDATE cards 
        SET quantity = ?, condition = ?, purchase_price = ?, 
            price_alert_threshold = ?, last_updated = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (quantity, condition, purchase_price, alert_threshold, card_id))
    
    # Recalculate total value
    card = conn.execute('SELECT current_price FROM cards WHERE id = ?', (card_id,)).fetchone()
    if card:
        total_value = card['current_price'] * quantity
        price_change = card['current_price'] - purchase_price
        conn.execute('''
            UPDATE cards 
            SET total_value = ?, price_change = ?
            WHERE id = ?
        ''', (total_value, price_change, card_id))
    
    conn.commit()
    conn.close()
    
    flash('Card updated successfully')
    return redirect(url_for('card_detail', card_id=card_id))

@app.route('/add_card', methods=['GET', 'POST'])
@login_required
def add_card():
    """Add new card to inventory"""
    if request.method == 'POST':
        conn = inventory_app.get_db_connection()
        
        # Get form data
        card_name = request.form.get('card_name')
        set_name = request.form.get('set_name', '')
        set_code = request.form.get('set_code', '')
        collector_number = request.form.get('collector_number', '')
        quantity = int(request.form.get('quantity', 1))
        is_foil = bool(request.form.get('is_foil'))
        condition = request.form.get('condition', 'Near Mint')
        purchase_price = float(request.form.get('purchase_price', 0))
        
        # Fetch current price and data from Scryfall
        try:
            card_data = fetch_scryfall_data_standalone(card_name, set_code, collector_number)
            current_price = float(card_data.get('usd_foil' if is_foil else 'usd', 0) or 0)
            market_url = card_data.get('market_url', '')
            image_url = card_data.get('image_url', '')
            rarity = card_data.get('rarity', '')
            colors = card_data.get('colors', '')
            mana_cost = card_data.get('mana_cost', '')
            mana_value = card_data.get('mana_value', 0)
            card_type = card_data.get('card_type', '')
        except:
            current_price = 0
            market_url = ''
            image_url = ''
            rarity = ''
            colors = ''
            mana_cost = ''
            mana_value = 0
            card_type = ''
        
        total_value = current_price * quantity
        price_change = current_price - purchase_price
        
        # Insert card
        try:
            cursor = conn.execute('''
                INSERT INTO cards 
                (card_name, set_name, set_code, collector_number, quantity, is_foil, 
                 condition, purchase_price, current_price, price_change, total_value, 
                 market_url, image_url, image_url_back, rarity, colors, mana_cost, mana_value, card_type, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (card_name, set_name, set_code, collector_number, quantity, is_foil,
                  condition, purchase_price, current_price, price_change, total_value,
                  market_url, image_url, card_data.get('image_url_back', ''), rarity, colors, mana_cost, mana_value, card_type, get_current_user_id()))
            
            card_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            # Auto-update price and metadata for the newly added card
            updated_count = update_card_prices_and_metadata([card_id])
            if updated_count > 0:
                flash(f'Added {card_name} to inventory and updated price/metadata')
            else:
                flash(f'Added {card_name} to inventory (price update failed)')
            
        except sqlite3.IntegrityError:
            conn.close()
            flash(f'Card {card_name} already exists with these specifications')
        return redirect(url_for('index'))
    
    return render_template('add_card.html')

@app.route('/import_csv', methods=['POST'])
@login_required
def import_csv():
    """Import CSV file to database with optional template creation and background processing"""
    current_user_id = get_current_user_id()
    
    # Get template creation options
    create_template = request.form.get('create_template', False)
    template_name = request.form.get('template_name', '')
    make_public = request.form.get('make_public', False)
    
    # Read CSV file
    df = None
    try:
        # Check if file was uploaded
        if 'csv_file' in request.files:
            file = request.files['csv_file']
            if file.filename:
                df = pd.read_csv(file)
                logger.info(f"CSV uploaded with {len(df)} rows and columns: {list(df.columns)}")
            else:
                flash('No file selected')
                return redirect(url_for('index'))
        else:
            # Fallback to file path
            csv_path = request.form.get('csv_path')
            if not csv_path:
                flash('No CSV file provided')
                return redirect(url_for('index'))
            
            df = pd.read_csv(csv_path)
            logger.info(f"CSV loaded from path: {csv_path}")
            
    except Exception as e:
        flash(f'Error reading CSV file: {e}')
        return redirect(url_for('index'))
    
    if df is None or len(df) == 0:
        flash('CSV file is empty or could not be read')
        return redirect(url_for('index'))
    
    # Start background import process
    def background_csv_import(dataframe, user_id, create_tmpl, tmpl_name, make_pub):
        """Background CSV import with progress tracking and auto-price updates"""
        try:
            # Initialize progress
            progress_state[user_id] = {
                'type': 'start',
                'total': len(dataframe),
                'message': f'Starting import of {len(dataframe)} cards...',
                'phase': 'preprocessing'
            }
            
            # Process CSV data (same as before but with progress updates)
            df_processed = preprocess_csv_data(dataframe, user_id)
            
            # Import cards with progress tracking
            imported_count, imported_card_ids = import_cards_with_progress(df_processed, user_id)
            
            # Auto-update prices and metadata
            if imported_card_ids:
                progress_state[user_id] = {
                    'type': 'progress',
                    'message': f'Fetching prices and images for {len(imported_card_ids)} cards...',
                    'phase': 'price_update',
                    'current': 0,
                    'total': len(imported_card_ids)
                }
                
                updated_count = update_card_prices_and_metadata_with_progress(imported_card_ids, user_id)
            else:
                updated_count = 0
            
            # Create template if requested
            template_id = None
            if create_tmpl and tmpl_name:
                try:
                    template_id = create_collection_template(
                        df=df_processed,
                        template_name=tmpl_name,
                        description=f"Collection imported from CSV with {imported_count} cards",
                        user_id=user_id,
                        make_public=bool(make_pub)
                    )
                except Exception as e:
                    logger.error(f"Template creation failed: {e}")
            
            # Final completion message
            template_msg = f" Template '{tmpl_name}' created." if template_id else ""
            progress_state[user_id] = {
                'type': 'complete',
                'message': f'Successfully imported {imported_count} cards with {updated_count} price updates.{template_msg}',
                'imported_count': imported_count,
                'updated_count': updated_count,
                'total': len(dataframe)
            }
            
            # Clean up
            active_updates[user_id] = False
            
        except Exception as e:
            logger.error(f"CSV import error: {e}")
            progress_state[user_id] = {
                'type': 'error',
                'message': f'Import failed: {str(e)}',
                'error': str(e)
            }
            active_updates[user_id] = False
    
    # Mark import as active and start background thread
    active_updates[current_user_id] = True
    threading.Thread(target=background_csv_import, args=(df, current_user_id, create_template, template_name, make_public), daemon=True).start()
    
    flash('CSV import started! Progress will be shown below.')
    return redirect(url_for('index'))

def preprocess_csv_data(df, user_id):
    """Preprocess CSV data with column mapping"""
    # Log all columns for debugging
    logger.info(f"Original CSV columns: {list(df.columns)}")
    
    # Flexible column mapping to handle different CSV formats
    column_mapping = {}
    
    # Direct mapping for Manabox CSV format
    manabox_mapping = {
        'Name': 'card_name',
        'Set code': 'set_code', 
        'Set name': 'set_name',
        'Collector number': 'collector_number',
        'Foil': 'is_foil',
        'Quantity': 'quantity',
        'Condition': 'condition',
        'Language': 'language',
        'Purchase price': 'purchase_price'
    }
    
    # Apply direct mapping
    for original_col, target_col in manabox_mapping.items():
        if original_col in df.columns:
            column_mapping[original_col] = target_col
            logger.info(f"Mapped {original_col} to {target_col}")
    
    # Apply column mapping
    df = df.rename(columns=column_mapping)
    logger.info(f"Columns after mapping: {list(df.columns)}")
    
    # Fill missing required columns
    if 'card_name' not in df.columns:
        # Try to find the first column that might be card names
        for col in df.columns:
            if df[col].dtype == 'object':  # String column
                logger.info(f"Using column '{col}' as card_name")
                df['card_name'] = df[col]
                break
        else:
            raise ValueError(f'Could not identify card name column. Available columns: {list(df.columns)}')
    
    # Set defaults for missing columns
    df['set_name'] = df.get('set_name', '')
    df['set_code'] = df.get('set_code', '')
    df['collector_number'] = df.get('collector_number', '')
    df['quantity'] = df.get('quantity', 1)
    df['is_foil'] = df.get('is_foil', False)
    df['condition'] = df.get('condition', 'Near Mint')
    df['language'] = df.get('language', 'English')
    df['purchase_price'] = df.get('purchase_price', 0)
    df['current_price'] = 0.0
    df['price_change'] = 0.0
    df['total_value'] = 0.0
    df['last_updated'] = datetime.now().isoformat()
    
    # Handle rarity from Manabox CSV if available
    if 'Rarity' in df.columns:
        df['rarity'] = df['Rarity'].str.title()
    else:
        df['rarity'] = ''
    
    # Show first few rows for debugging
    logger.info(f"First 3 rows of data:")
    for i in range(min(3, len(df))):
        logger.info(f"Row {i}: {dict(df.iloc[i])}")
    
    return df

# Import CSV helper functions  
from csv_import_helpers import preprocess_csv_data, import_cards_with_progress, update_card_prices_and_metadata_with_progress

@app.route('/collections')
@login_required  
def collections():
    """View available collection templates"""
    conn = inventory_app.get_db_connection()
    user_id = get_current_user_id()
    
    # Get public templates and user's own templates
    templates = conn.execute('''
        SELECT ct.*, u.email as creator_email,
               (SELECT COUNT(*) FROM card_templates WHERE template_id = ct.id) as card_count,
               (SELECT COUNT(*) FROM user_collection_instances WHERE template_id = ct.id AND user_id = ?) as is_imported
        FROM collection_templates ct
        JOIN users u ON ct.created_by = u.id
                set_code = str(row['set_code']).strip() if pd.notna(row['set_code']) else ''
                collector_number = str(row['collector_number']).strip() if pd.notna(row['collector_number']) else ''
                
                # Convert condition format (near_mint -> Near Mint)
                condition_raw = str(row['condition']).strip() if pd.notna(row['condition']) else 'near_mint'
                condition = condition_raw.replace('_', ' ').title()
                
                # Convert language code (en -> English) 
                language_raw = str(row['language']).strip() if pd.notna(row['language']) else 'en'
                language = 'English' if language_raw == 'en' else language_raw
                
                # Get rarity from CSV
                rarity = str(row.get('rarity', '')).strip() if pd.notna(row.get('rarity', '')) else ''
                
                # Handle numeric fields safely
                try:
                    quantity = int(row['quantity']) if pd.notna(row['quantity']) else 1
                except (ValueError, TypeError):
                    quantity = 1
                
                try:
                    # Handle purchase_price - might be a Series due to duplicate mapping
                    if hasattr(row['purchase_price'], 'iloc'):
                        # It's a Series, take the first value
                        purchase_price = float(row['purchase_price'].iloc[0]) if pd.notna(row['purchase_price'].iloc[0]) else 0
                    else:
                        purchase_price = float(row['purchase_price']) if pd.notna(row['purchase_price']) else 0
                except (ValueError, TypeError, AttributeError):
                    purchase_price = 0
                
                logger.info(f"Importing card: {card_name}, Set: {set_name}, Qty: {quantity}")
                
                cursor = conn.execute('''
                    INSERT OR REPLACE INTO cards 
                    (card_name, set_name, set_code, collector_number, quantity, is_foil, 
                     condition, language, purchase_price, current_price, price_change, 
                     total_value, rarity, image_url_back, user_id, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    card_name,
                    set_name,
                    set_code,
                    collector_number,
                    quantity,
                    is_foil,
                    condition,
                    language,
                    purchase_price,
                    0.0,  # current_price will be updated later
                    0.0,  # price_change
                    0.0,  # total_value
                    rarity,
                    '',   # image_url_back - will be updated later
                    get_current_user_id(),  # Associate with current user
                    datetime.now().isoformat()
                ))
                imported_card_ids.append(cursor.lastrowid)
                imported_count += 1
                
            except Exception as e:
                error_count += 1
                logger.error(f"Could not import row {idx} (card: {row.get('card_name', 'Unknown')}): {e}")
                logger.error(f"Row data: {dict(row)}")
        
        conn.commit()
        conn.close()
        
        # Create collection template if requested
        create_template = request.form.get('create_template', False)
        template_name = request.form.get('template_name', '')
        make_public = request.form.get('make_public', False)
        
        template_id = None
        if create_template and template_name:
            try:
                # Use the same DataFrame that was imported
                template_id = create_collection_template(
                    df=df,
                    template_name=template_name,
                    description=f"Collection imported from CSV with {imported_count} cards",
                    make_public=bool(make_public)
                )
                logger.info(f"Created collection template '{template_name}' with ID {template_id}")
            except Exception as e:
                logger.error(f"Failed to create collection template: {e}")
        
        # Auto-update prices and metadata for imported cards
        if imported_card_ids:
            logger.info(f"Starting auto-update for {len(imported_card_ids)} imported cards")
            updated_count = update_card_prices_and_metadata(imported_card_ids)
            
            template_msg = f" Template '{template_name}' created." if template_id else ""
            flash(f'Successfully imported {imported_count} cards from CSV ({error_count} errors). Updated {updated_count} cards with current prices/metadata.{template_msg}')
            logger.info(f"Import complete: {imported_count} cards imported, {error_count} errors, {updated_count} cards updated with prices")
        else:
            template_msg = f" Template '{template_name}' created." if template_id else ""
            flash(f'Successfully imported {imported_count} cards from CSV ({error_count} errors){template_msg}')
            logger.info(f"Import complete: {imported_count} cards imported, {error_count} errors")
        
    except Exception as e:
        error_msg = f'Error importing CSV: {str(e)}'
        flash(error_msg)
        logger.error(f"CSV import error: {e}")
    
    return redirect(url_for('index'))

@app.route('/collections')
@login_required  
def collections():
    """View available collection templates"""
    conn = inventory_app.get_db_connection()
    user_id = get_current_user_id()
    
    # Get public templates and user's own templates
    templates = conn.execute('''
        SELECT ct.*, u.email as creator_email,
               (SELECT COUNT(*) FROM card_templates WHERE template_id = ct.id) as card_count,
               (SELECT COUNT(*) FROM user_collection_instances WHERE template_id = ct.id AND user_id = ?) as is_imported
        FROM collection_templates ct
        JOIN users u ON ct.created_by = u.id
        WHERE ct.is_public = 1 OR ct.created_by = ?
        ORDER BY ct.created_at DESC
    ''', (user_id, user_id)).fetchall()
    
    # Get user's imported collections
    user_collections = conn.execute('''
        SELECT uci.*, ct.name as template_name, ct.description,
               (SELECT COUNT(*) FROM cards WHERE user_id = ? AND source_template_id = ct.id) as card_count
        FROM user_collection_instances uci
        JOIN collection_templates ct ON uci.template_id = ct.id
        WHERE uci.user_id = ?
        ORDER BY uci.imported_at DESC
    ''', (user_id, user_id)).fetchall()
    
    conn.close()
    
    return render_template('collections.html', templates=templates, user_collections=user_collections)

@app.route('/import_template/<int:template_id>')
@login_required
def import_template(template_id):
    """Import a collection template as user's independent collection"""
    user_id = get_current_user_id()
    
    # Check if template exists and is accessible
    conn = inventory_app.get_db_connection()
    template = conn.execute('''
        SELECT * FROM collection_templates 
        WHERE id = ? AND (is_public = 1 OR created_by = ?)
    ''', (template_id, user_id)).fetchone()
    conn.close()
    
    if not template:
        flash('Collection template not found or not accessible', 'error')
        return redirect(url_for('collections'))
    
    # Import template as user collection
    imported_count = import_template_as_user_collection(template_id, user_id)
    
    if imported_count > 0:
        flash(f'Successfully imported {imported_count} cards from "{template["name"]}" collection')
    else:
        flash('Collection already imported or no cards to import')
    
    return redirect(url_for('index'))

@app.route('/share_template/<int:template_id>')
@login_required
def share_template(template_id):
    """Make a template public for sharing"""
    user_id = get_current_user_id()
    
    conn = inventory_app.get_db_connection()
    
    # Verify user owns this template
    template = conn.execute('SELECT * FROM collection_templates WHERE id = ? AND created_by = ?', 
                           (template_id, user_id)).fetchone()
    
    if not template:
        flash('Template not found or you do not have permission to share it', 'error')
        conn.close()
        return redirect(url_for('collections'))
    
    # Make template public
    conn.execute('UPDATE collection_templates SET is_public = 1 WHERE id = ?', (template_id,))
    conn.commit()
    conn.close()
    
    flash(f'Collection template "{template["name"]}" is now public and can be imported by other users')
    return redirect(url_for('collections'))

@app.route('/delete_template/<int:template_id>', methods=['POST'])
@login_required
def delete_template(template_id):
    """Delete a collection template (only if user created it)"""
    user_id = get_current_user_id()
    
    conn = inventory_app.get_db_connection()
    
    # Verify user owns this template
    template = conn.execute('SELECT * FROM collection_templates WHERE id = ? AND created_by = ?', 
                           (template_id, user_id)).fetchone()
    
    if not template:
        flash('Template not found or you do not have permission to delete it', 'error')
        conn.close()
        return redirect(url_for('collections'))
    
    # Delete template and associated data
    conn.execute('DELETE FROM card_templates WHERE template_id = ?', (template_id,))
    conn.execute('DELETE FROM user_collection_instances WHERE template_id = ?', (template_id,))
    conn.execute('DELETE FROM collection_templates WHERE id = ?', (template_id,))
    
    conn.commit()
    conn.close()
    
    flash(f'Collection template "{template["name"]}" has been deleted')
    return redirect(url_for('collections'))

def fetch_scryfall_data_standalone(card_name: str, set_code: str = None, collector_number: str = None) -> dict:
    """Fetch complete card data from Scryfall including prices and metadata
    
    Enhanced to handle card variants by using collector number when available
    """
    try:
        # If we have collector number and set code, use the more specific endpoint first
        if collector_number and set_code:
            try:
                specific_url = f"https://api.scryfall.com/cards/{set_code.lower()}/{collector_number}"
                response = requests.get(specific_url)
                time.sleep(0.05)  # Reduced rate limiting
                
                if response.status_code == 200:
                    data = response.json()
                    # Verify the card name matches (accounting for variations)
                    if cards_match(card_name, data.get('name', '')):
                        return extract_card_data(data)
                    else:
                        logger.warning(f"Collector number match found but name mismatch: '{card_name}' vs '{data.get('name', '')}'")
            except Exception as e:
                logger.debug(f"Collector number lookup failed for {card_name}: {e}")
        
        # Fall back to name-based search
        base_url = "https://api.scryfall.com/cards/named"
        params = {
            'fuzzy': card_name,
            'format': 'json'
        }
        
        if set_code:
            params['set'] = set_code.lower()
        
        response = requests.get(base_url, params=params)
        time.sleep(0.1)  # Rate limiting
        
        if response.status_code == 200:
            data = response.json()
            return extract_card_data(data)
        else:
            logger.warning(f"Could not fetch data for {card_name}: {response.status_code}")
            return {'usd': 0, 'usd_foil': 0, 'rarity': '', 'colors': '', 'mana_cost': '', 'mana_value': 0, 'card_type': ''}
            
    except Exception as e:
        logger.error(f"Error fetching data for {card_name}: {e}")
        return {'usd': 0, 'usd_foil': 0, 'rarity': '', 'colors': '', 'mana_cost': '', 'mana_value': 0, 'card_type': ''}

def cards_match(name1: str, name2: str) -> bool:
    """Check if two card names match, accounting for common variations"""
    name1 = name1.strip().lower()
    name2 = name2.strip().lower()
    
    # Direct match
    if name1 == name2:
        return True
    
    # Remove common suffixes/prefixes for variants
    variants = [' (borderless)', ' (showcase)', ' (extended art)', ' (retro frame)', 
               ' (full art)', ' (alternate art)', ' (promo)', ' (foil etched)']
    
    for variant in variants:
        name1_clean = name1.replace(variant, '')
        name2_clean = name2.replace(variant, '')
        
        if name1_clean == name2_clean:
            return True
    
    # Handle double-faced cards (// separator)
    if '//' in name1 or '//' in name2:
        name1_parts = [part.strip() for part in name1.split('//')]
        name2_parts = [part.strip() for part in name2.split('//')]
        
        # Check if first parts match
        if name1_parts[0] == name2_parts[0]:
            return True
    
    return False

def extract_card_data(data: dict) -> dict:
    """Extract standardized card data from Scryfall response"""
    # Extract color information
    colors = data.get('colors', [])
    color_identity = data.get('color_identity', [])
    
    # Determine color category
    if not colors:
        color_category = 'Colorless'
    elif len(colors) == 1:
        color_map = {'W': 'White', 'U': 'Blue', 'B': 'Black', 'R': 'Red', 'G': 'Green'}
        color_category = color_map.get(colors[0], 'Other')
    else:
        color_category = 'Multicolor'
    
    # Handle image URL - double-faced cards have different structure
    image_url = ''
    image_url_back = ''
    
    if 'image_uris' in data:
        # Single-faced card
        image_url = data['image_uris'].get('normal', '')
    elif 'card_faces' in data and len(data['card_faces']) > 0:
        # Double-faced card - get both faces
        first_face = data['card_faces'][0]
        if 'image_uris' in first_face:
            image_url = first_face['image_uris'].get('normal', '')
        
        # Get second face if it exists
        if len(data['card_faces']) > 1:
            second_face = data['card_faces'][1]
            if 'image_uris' in second_face:
                image_url_back = second_face['image_uris'].get('normal', '')
    
    # For double-faced cards, handle mana cost and type from first face if not at top level
    mana_cost = data.get('mana_cost', '')
    card_type = data.get('type_line', '')
    
    if not mana_cost and 'card_faces' in data and len(data['card_faces']) > 0:
        mana_cost = data['card_faces'][0].get('mana_cost', '')
    
    if not card_type and 'card_faces' in data and len(data['card_faces']) > 0:
        card_type = data['card_faces'][0].get('type_line', '')

    return {
        'usd': data.get('prices', {}).get('usd', 0),
        'usd_foil': data.get('prices', {}).get('usd_foil', 0),
        'eur': data.get('prices', {}).get('eur', 0),
        'tix': data.get('prices', {}).get('tix', 0),
        'market_url': data.get('purchase_uris', {}).get('tcgplayer', ''),
        'image_url': image_url,
        'image_url_back': image_url_back,
        'rarity': data.get('rarity', '').title(),
        'colors': color_category,
        'mana_cost': mana_cost,
        'mana_value': data.get('cmc', 0),
        'card_type': card_type
    }

@app.route('/update_prices')
@login_required
def update_prices():
    """Update card prices (prioritizing cards missing metadata)"""
    conn = inventory_app.get_db_connection()
    # Prioritize cards missing rarity, colors, mana, or card type data for current user
    current_user_id = get_current_user_id()
    # First check if user has any cards at all
    total_cards = conn.execute('SELECT COUNT(*) FROM cards WHERE user_id = ?', (current_user_id,)).fetchone()[0]
    
    if total_cards == 0:
        conn.close()
        flash('No cards found in your collection. Import some cards first.')
        return redirect(url_for('index'))
    
    cards = conn.execute('''
        SELECT * FROM cards 
        WHERE user_id = ? AND (rarity IS NULL OR rarity = '' OR colors IS NULL OR colors = '' 
           OR mana_cost IS NULL OR mana_cost = '' OR card_type IS NULL OR card_type = '')
        ORDER BY total_value DESC
        LIMIT 200
    ''', (current_user_id,)).fetchall()
    
    updated_count = 0
    
    for card in cards:
        try:
            logger.info(f"Updating price for: {card['card_name']}")
            card_data = fetch_scryfall_data_standalone(card['card_name'], card['set_code'], card['collector_number'] if card['collector_number'] else None)
            current_price = float(card_data.get('usd_foil' if card['is_foil'] else 'usd', 0) or 0)
            total_value = current_price * card['quantity']
            price_change = current_price - (card['purchase_price'] or 0)
            
            logger.info(f"Price found: ${current_price} for {card['card_name']}")
            
            # Check for price alerts
            if card['price_alert_threshold'] > 0 and card['current_price']:
                price_change_percent = ((current_price - card['current_price']) / card['current_price']) * 100
                
                if abs(price_change_percent) >= card['price_alert_threshold']:
                    conn.execute('''
                        INSERT INTO price_alerts (card_id, alert_type, threshold_value, current_value)
                        VALUES (?, ?, ?, ?)
                    ''', (card['id'], 'price_change', card['price_alert_threshold'], price_change_percent))
            
            # Update card with all data
            conn.execute('''
                UPDATE cards 
                SET current_price = ?, total_value = ?, price_change = ?, 
                    market_url = ?, image_url = ?, image_url_back = ?, rarity = ?, colors = ?, 
                    mana_cost = ?, mana_value = ?, card_type = ?, last_updated = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (current_price, total_value, price_change, 
                  card_data.get('market_url', ''), card_data.get('image_url', ''),
                  card_data.get('image_url_back', ''), card_data.get('rarity', ''), card_data.get('colors', ''),
                  card_data.get('mana_cost', ''), card_data.get('mana_value', 0),
                  card_data.get('card_type', ''), card['id']))
            
            updated_count += 1
            
        except Exception as e:
            logger.error(f"Could not update price for {card['card_name']}: {e}")
    
    conn.commit()
    conn.close()
    
    if updated_count == 0:
        missing_cards_count = len(cards)
        if missing_cards_count == 0:
            flash(f'All {total_cards} cards already have complete metadata!')
        else:
            flash(f'Found {missing_cards_count} cards with missing metadata, but none could be updated. Check logs for errors.')
    else:
        flash(f'Updated metadata for {updated_count} cards (prioritizing missing data)')
    
    return redirect(url_for('index'))

@app.route('/update_all_prices')
@login_required
def update_all_prices():
    """Update ALL card prices (background process)"""
    # Get user ID in the main thread context
    current_user_id = get_current_user_id()
    
    def bulk_update(user_id):
        conn = inventory_app.get_db_connection()
        cards = conn.execute('SELECT * FROM cards WHERE user_id = ?', (user_id,)).fetchall()
        
        # Store initial progress
        start_data = {
            'type': 'start',
            'total': len(cards),
            'message': f'Starting price update for {len(cards)} cards...'
        }
        progress_state[user_id] = start_data
        
        updated_count = 0
        for i, card in enumerate(cards):
            try:
                logger.info(f"Updating {i+1}/{len(cards)}: {card['card_name']}")
                
                # Store progress update
                progress_data = {
                    'type': 'progress',
                    'current': i + 1,
                    'total': len(cards),
                    'card_name': card['card_name'],
                    'message': f'Updating {i+1}/{len(cards)}: {card["card_name"]}',
                    'updated_count': updated_count
                }
                progress_state[user_id] = progress_data
                
                card_data = fetch_scryfall_data_standalone(card['card_name'], card['set_code'], card['collector_number'] if card['collector_number'] else None)
                current_price = float(card_data.get('usd_foil' if card['is_foil'] else 'usd', 0) or 0)
                total_value = current_price * card['quantity']
                price_change = current_price - (card['purchase_price'] or 0)
                
                conn.execute('''
                    UPDATE cards 
                    SET current_price = ?, total_value = ?, price_change = ?, 
                        market_url = ?, image_url = ?, rarity = ?, colors = ?, 
                        mana_cost = ?, mana_value = ?, card_type = ?, last_updated = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (current_price, total_value, price_change, 
                      card_data.get('market_url', ''), card_data.get('image_url', ''),
                      card_data.get('rarity', ''), card_data.get('colors', ''),
                      card_data.get('mana_cost', ''), card_data.get('mana_value', 0),
                      card_data.get('card_type', ''), card['id']))
                
                updated_count += 1
                
                # Commit every 10 cards
                if (i + 1) % 10 == 0:
                    conn.commit()
                    
            except Exception as e:
                logger.error(f"Error updating {card['card_name']}: {e}")
                # Store error in progress state if needed
                progress_state[user_id] = {
                    'type': 'error',
                    'card_name': card['card_name'],
                    'message': f'Error updating {card["card_name"]}: {str(e)}'
                }
        
        conn.commit()
        conn.close()
        logger.info("Bulk price update completed!")
        
        # Store completion message
        complete_data = {
            'type': 'complete',
            'updated_count': updated_count,
            'total': len(cards),
            'message': f'Price update completed! Updated {updated_count} of {len(cards)} cards.'
        }
        progress_state[user_id] = complete_data
        
        # Clean up
        active_updates[user_id] = False
    
    # Mark update as active for this user
    active_updates[current_user_id] = True
    
    # Start background update with user ID parameter
    threading.Thread(target=bulk_update, args=(current_user_id,), daemon=True).start()
    
    flash('Started background price update for all cards. Check progress below.')
    return redirect(url_for('index'))

@app.route('/progress_status')
@login_required
def progress_status():
    """REST endpoint to check progress status (fallback for SSE issues)"""
    user_id = get_current_user_id()
    
    # Check if update is active
    if user_id not in active_updates or not active_updates.get(user_id, False):
        return jsonify({
            'active': False,
            'message': 'No active price update',
            'latest_progress': progress_state.get(user_id, None)
        })
    
    # Get latest progress from stored state
    latest_progress = progress_state.get(user_id, None)
    
    return jsonify({
        'active': True,
        'latest_progress': latest_progress,
        'message': 'Price update in progress'
    })

@app.route('/system_status')
def system_status():
    """System status check - no authentication required"""
    return jsonify({
        'active_updates_count': len([k for k, v in active_updates.items() if v]),
        'total_progress_states': len(progress_state),
        'server_time': time.time()
    })

@app.route('/debug_session')
def debug_session():
    """Debug session information - no authentication required"""
    return jsonify({
        'session_data': dict(session),
        'user_id': session.get('user_id'),
        'user_email': session.get('user_email'),
        'has_session': bool(session),
        'session_keys': list(session.keys())
    })

@app.route('/alerts')
@login_required
def alerts():
    """View price alerts"""
    conn = inventory_app.get_db_connection()
    
    alerts = conn.execute('''
        SELECT pa.*, c.card_name, c.set_name, c.current_price, c.total_value
        FROM price_alerts pa
        JOIN cards c ON pa.card_id = c.id
        ORDER BY pa.triggered_at DESC
    ''').fetchall()
    
    conn.close()
    
    return render_template('alerts.html', alerts=alerts)

@app.route('/mark_alert_read/<int:alert_id>')
def mark_alert_read(alert_id):
    """Mark price alert as read"""
    conn = inventory_app.get_db_connection()
    conn.execute('UPDATE price_alerts SET is_read = 1 WHERE id = ?', (alert_id,))
    conn.commit()
    conn.close()
    
    return redirect(url_for('alerts'))

@app.route('/delete_card/<int:card_id>', methods=['POST'])
def delete_card(card_id):
    """Delete card from inventory"""
    conn = inventory_app.get_db_connection()
    conn.execute('DELETE FROM cards WHERE id = ?', (card_id,))
    conn.commit()
    conn.close()
    
    flash('Card deleted from inventory')
    return redirect(url_for('index'))

@app.route('/api/cards')
@login_required
def api_cards():
    """API endpoint for cards data"""
    user_id = get_current_user_id()
    conn = inventory_app.get_db_connection()
    cards = conn.execute('SELECT * FROM cards WHERE user_id = ? ORDER BY total_value DESC', (user_id,)).fetchall()
    conn.close()
    
    return jsonify([dict(card) for card in cards])

@app.route('/api/card/<int:card_id>/image')
def api_card_image(card_id):
    """API endpoint for card image URL"""
    conn = inventory_app.get_db_connection()
    card = conn.execute('SELECT image_url FROM cards WHERE id = ?', (card_id,)).fetchone()
    conn.close()
    
    if card and card['image_url']:
        return jsonify({'image_url': card['image_url']})
    else:
        return jsonify({'image_url': None})

@app.route('/mass_update_prices', methods=['POST'])
@login_required
def mass_update_prices():
    """Mass update prices for selected cards"""
    try:
        data = request.get_json()
        card_ids = data.get('card_ids', [])
        
        if not card_ids:
            return jsonify({'success': False, 'error': 'No cards selected'})
        
        current_user_id = get_current_user_id()
        
        # Verify all cards belong to current user
        conn = inventory_app.get_db_connection()
        placeholders = ','.join(['?' for _ in card_ids])
        user_cards = conn.execute(f'SELECT id FROM cards WHERE id IN ({placeholders}) AND user_id = ?', card_ids + [current_user_id]).fetchall()
        conn.close()
        
        if len(user_cards) != len(card_ids):
            return jsonify({'success': False, 'error': 'Some cards do not belong to current user'})
        
        # Update prices
        updated_count = update_card_prices_and_metadata(card_ids)
        
        return jsonify({
            'success': True,
            'updated_count': updated_count
        })
        
    except Exception as e:
        logger.error(f"Mass update prices error: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/mass_delete', methods=['POST'])
@login_required
def mass_delete():
    """Mass delete selected cards"""
    try:
        data = request.get_json()
        card_ids = data.get('card_ids', [])
        
        if not card_ids:
            return jsonify({'success': False, 'error': 'No cards selected'})
        
        current_user_id = get_current_user_id()
        
        # Delete cards belonging to current user
        conn = inventory_app.get_db_connection()
        placeholders = ','.join(['?' for _ in card_ids])
        
        # First verify they belong to user and get count
        user_cards = conn.execute(f'SELECT id FROM cards WHERE id IN ({placeholders}) AND user_id = ?', card_ids + [current_user_id]).fetchall()
        
        if not user_cards:
            conn.close()
            return jsonify({'success': False, 'error': 'No cards found or cards do not belong to current user'})
        
        # Delete the cards
        conn.execute(f'DELETE FROM cards WHERE id IN ({placeholders}) AND user_id = ?', card_ids + [current_user_id])
        deleted_count = conn.execute('SELECT changes()').fetchone()[0]
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'deleted_count': deleted_count
        })
        
    except Exception as e:
        logger.error(f"Mass delete error: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/delete_all_cards', methods=['POST'])
@login_required
def delete_all_cards():
    """Delete all cards for the current user"""
    try:
        current_user_id = get_current_user_id()
        
        conn = inventory_app.get_db_connection()
        
        # Count cards before deletion
        card_count = conn.execute('SELECT COUNT(*) FROM cards WHERE user_id = ?', (current_user_id,)).fetchone()[0]
        
        if card_count == 0:
            conn.close()
            return jsonify({'success': False, 'error': 'No cards found to delete'})
        
        # Delete all cards for the current user
        conn.execute('DELETE FROM cards WHERE user_id = ?', (current_user_id,))
        deleted_count = conn.execute('SELECT changes()').fetchone()[0]
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'deleted_count': deleted_count,
            'message': f'Successfully deleted {deleted_count} cards from your collection'
        })
        
    except Exception as e:
        logger.error(f"Delete all cards error: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/analyze_csv', methods=['POST'])
def analyze_csv():
    """Analyze CSV structure without importing"""
    # Check if file was uploaded
    if 'csv_file' in request.files:
        file = request.files['csv_file']
        if file.filename:
            try:
                df = pd.read_csv(file)
            except Exception as e:
                return jsonify({'error': f'Error reading CSV: {e}'})
        else:
            return jsonify({'error': 'No file selected'})
    else:
        return jsonify({'error': 'No file provided'})
    
    # Analyze the CSV structure
    analysis = {
        'total_rows': len(df),
        'columns': list(df.columns),
        'sample_data': {},
        'data_types': {}
    }
    
    # Get sample data and data types for each column
    for col in df.columns:
        analysis['sample_data'][col] = df[col].head(5).tolist()
        analysis['data_types'][col] = str(df[col].dtype)
    
    return jsonify(analysis)

@app.route('/update_rarity_from_csv', methods=['POST'])
def update_rarity_from_csv():
    """Update existing cards with rarity data from CSV"""
    if 'csv_file' not in request.files:
        flash('No CSV file provided')
        return redirect(url_for('index'))
    
    file = request.files['csv_file']
    if not file.filename:
        flash('No file selected')
        return redirect(url_for('index'))
    
    try:
        # Read CSV
        df = pd.read_csv(file)
        
        # Create mapping from CSV
        rarity_mapping = {}
        for _, row in df.iterrows():
            card_name = str(row['Name']).strip()
            set_code = str(row['Set code']).strip()
            rarity = str(row['Rarity']).strip().title()
            
            key = (card_name, set_code)
            rarity_mapping[key] = rarity
        
        # Update database
        conn = inventory_app.get_db_connection()
        updated_count = 0
        
        cards = conn.execute('SELECT * FROM cards').fetchall()
        for card in cards:
            key = (card['card_name'], card['set_code'])
            if key in rarity_mapping:
                conn.execute('''
                    UPDATE cards SET rarity = ? WHERE id = ?
                ''', (rarity_mapping[key], card['id']))
                updated_count += 1
        
        conn.commit()
        conn.close()
        
        flash(f'Updated rarity for {updated_count} cards')
        
    except Exception as e:
        flash(f'Error updating rarity: {e}')
        logger.error(f"Rarity update error: {e}")
    
    return redirect(url_for('index'))

def background_price_monitor():
    """Background thread to monitor prices and send alerts"""
    while True:
        try:
            conn = inventory_app.get_db_connection()
            cards_with_alerts = conn.execute('''
                SELECT * FROM cards 
                WHERE price_alert_threshold > 0
            ''').fetchall()
            
            for card in cards_with_alerts:
                try:
                    prices = fetch_scryfall_prices_standalone(card['card_name'], card['set_code'])
                    new_price = float(prices.get('usd_foil' if card['is_foil'] else 'usd', 0) or 0)
                    
                    if card['current_price'] and card['current_price'] > 0:
                        price_change_percent = ((new_price - card['current_price']) / card['current_price']) * 100
                        
                        if abs(price_change_percent) >= card['price_alert_threshold']:
                            # Check if we already sent an alert recently (within 24 hours)
                            recent_alert = conn.execute('''
                                SELECT id FROM price_alerts 
                                WHERE card_id = ? AND triggered_at > datetime('now', '-1 day')
                            ''', (card['id'],)).fetchone()
                            
                            if not recent_alert:
                                conn.execute('''
                                    INSERT INTO price_alerts (card_id, alert_type, threshold_value, current_value)
                                    VALUES (?, ?, ?, ?)
                                ''', (card['id'], 'price_change', card['price_alert_threshold'], price_change_percent))
                                
                                logger.info(f"Price alert triggered for {card['card_name']}: {price_change_percent:.1f}%")
                    
                    # Update current price
                    total_value = new_price * card['quantity']
                    price_change = new_price - (card['purchase_price'] or 0)
                    
                    conn.execute('''
                        UPDATE cards 
                        SET current_price = ?, total_value = ?, price_change = ?, last_updated = CURRENT_TIMESTAMP
                        WHERE id = ?
                    ''', (new_price, total_value, price_change, card['id']))
                    
                except Exception as e:
                    logger.warning(f"Error updating price for {card['card_name']}: {e}")
            
            conn.commit()
            conn.close()
            
            # Sleep for 1 hour before next check
            time.sleep(3600)
            
        except Exception as e:
            logger.error(f"Background price monitor error: {e}")
            time.sleep(300)  # Sleep 5 minutes on error

# Start background price monitoring
price_monitor_thread = threading.Thread(target=background_price_monitor, daemon=True)
price_monitor_thread.start()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)