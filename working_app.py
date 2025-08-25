from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import pandas as pd
import requests
import time
import sqlite3
import threading
import logging
import hashlib
from datetime import datetime, timedelta
from functools import wraps

# Initialize Flask app
app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global state for progress tracking
progress_state = {}
active_updates = {}

class TCGInventoryManager:
    def __init__(self, db_path='inventory.db'):
        self.db_path = db_path
        self.init_database()
    
    def get_db_connection(self):
        """Get database connection with proper configuration"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys = ON')
        return conn
    
    def init_database(self):
        """Initialize database with all necessary tables"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        # Cards table
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
                image_url_back TEXT,
                rarity TEXT,
                colors TEXT,
                mana_cost TEXT,
                mana_value INTEGER DEFAULT 0,
                card_type TEXT,
                price_alert_threshold REAL DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                user_id INTEGER NOT NULL,
                template_hash TEXT,
                source_template_id INTEGER,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Price alerts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS price_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_id INTEGER NOT NULL,
                alert_type TEXT NOT NULL,
                threshold_value REAL NOT NULL,
                current_value REAL NOT NULL,
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
        
        # Collection templates table
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
        
        conn.commit()
        conn.close()

# Initialize the inventory manager
inventory_app = TCGInventoryManager()

def fetch_scryfall_data_standalone(card_name, set_code=None, collector_number=None):
    """Fetch card data from Scryfall API with enhanced double-faced card support"""
    import requests
    import time
    
    try:
        # Build search query  
        query = f'!"{card_name}"'
        if set_code:
            query += f' set:{set_code}'
        if collector_number:
            query += f' cn:{collector_number}'
        
        # Make request to Scryfall
        url = f'https://api.scryfall.com/cards/search?q={requests.utils.quote(query)}'
        response = requests.get(url, timeout=10)
        
        # Rate limiting respect
        time.sleep(0.1)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('total_cards', 0) > 0:
                card_data = data['data'][0]
                return extract_card_data(card_data)
        
        # Fallback: try fuzzy search without set/collector number
        if set_code or collector_number:
            fallback_query = f'!"{card_name}"'
            fallback_url = f'https://api.scryfall.com/cards/search?q={requests.utils.quote(fallback_query)}'
            fallback_response = requests.get(fallback_url, timeout=10)
            
            time.sleep(0.1)
            
            if fallback_response.status_code == 200:
                fallback_data = fallback_response.json()
                if fallback_data.get('total_cards', 0) > 0:
                    card_data = fallback_data['data'][0]
                    return extract_card_data(card_data)
        
        return {}
        
    except Exception as e:
        logger.error(f"Scryfall API error for {card_name}: {e}")
        return {}

def extract_card_data(data):
    """Extract relevant data from Scryfall API response with double-faced card support"""
    try:
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
        
        # Extract basic data
        card_info = {
            'usd': data.get('prices', {}).get('usd'),
            'usd_foil': data.get('prices', {}).get('usd_foil'),
            'market_url': data.get('scryfall_uri', ''),
            'image_url': image_url,
            'image_url_back': image_url_back,
            'rarity': data.get('rarity', '').title(),
            'colors': ','.join(data.get('colors', [])),
            'mana_cost': data.get('mana_cost', ''),
            'mana_value': data.get('mana_value', 0),
            'card_type': data.get('type_line', '')
        }
        
        # Handle double-faced cards for mana cost and type
        if 'card_faces' in data and len(data['card_faces']) > 0:
            first_face = data['card_faces'][0]
            if not card_info['mana_cost'] and 'mana_cost' in first_face:
                card_info['mana_cost'] = first_face.get('mana_cost', '')
            if not card_info['card_type'] and 'type_line' in first_face:
                card_info['card_type'] = first_face.get('type_line', '')
        
        return card_info
        
    except Exception as e:
        logger.error(f"Error extracting card data: {e}")
        return {}

def create_collection_template(df, template_name, description, user_id, make_public=False):
    """Create a collection template from DataFrame"""
    import hashlib
    
    # Generate template hash
    template_data = f"{template_name}_{user_id}_{len(df)}_{datetime.now().isoformat()}"
    template_hash = hashlib.sha256(template_data.encode()).hexdigest()
    
    conn = inventory_app.get_db_connection()
    
    try:
        # Create template
        cursor = conn.execute('''
            INSERT INTO collection_templates (name, description, template_hash, created_by, is_public)
            VALUES (?, ?, ?, ?, ?)
        ''', (template_name, description, template_hash, user_id, make_public))
        
        template_id = cursor.lastrowid
        
        # Add card templates
        for _, row in df.iterrows():
            card_hash = hashlib.sha256(f"{row['card_name']}_{row.get('set_code', '')}_{row.get('collector_number', '')}".encode()).hexdigest()
            
            conn.execute('''
                INSERT INTO card_templates 
                (template_id, card_name, set_name, set_code, collector_number, is_foil,
                 condition, language, quantity, rarity, colors, mana_cost, mana_value, 
                 card_type, template_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                template_id, row['card_name'], row.get('set_name', ''), row.get('set_code', ''),
                row.get('collector_number', ''), row.get('is_foil', False), row.get('condition', 'Near Mint'),
                row.get('language', 'English'), row.get('quantity', 1), row.get('rarity', ''),
                row.get('colors', ''), row.get('mana_cost', ''), row.get('mana_value', 0),
                row.get('card_type', ''), card_hash
            ))
        
        conn.commit()
        return template_id
        
    finally:
        conn.close()

# Helper functions
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, password_hash):
    return hashlib.sha256(password.encode()).hexdigest() == password_hash

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_current_user_id():
    return session.get('user_id')

# Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        conn = inventory_app.get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()
        
        if user and verify_password(password, user['password_hash']):
            session['user_id'] = user['id']
            session['user_email'] = user['email']
            return redirect(url_for('index'))
        else:
            flash('Invalid email or password')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Passwords do not match')
            return render_template('register.html')
        
        try:
            conn = inventory_app.get_db_connection()
            conn.execute('INSERT INTO users (email, password_hash) VALUES (?, ?)', 
                        (email, hash_password(password)))
            conn.commit()
            conn.close()
            flash('Registration successful! Please log in.')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Email already exists')
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    user_id = get_current_user_id()
    conn = inventory_app.get_db_connection()
    
    # Get basic stats
    stats = conn.execute('''
        SELECT 
            COUNT(*) as total_cards,
            SUM(quantity) as total_quantity, 
            SUM(total_value) as total_value,
            AVG(current_price) as avg_price
        FROM cards WHERE user_id = ?
    ''', (user_id,)).fetchone()
    
    # Get cards with pagination
    page = int(request.args.get('page', 1))
    per_page = 50
    offset = (page - 1) * per_page
    
    cards = conn.execute('''
        SELECT * FROM cards WHERE user_id = ?
        ORDER BY total_value DESC 
        LIMIT ? OFFSET ?
    ''', (user_id, per_page, offset)).fetchall()
    
    total_cards = conn.execute('SELECT COUNT(*) FROM cards WHERE user_id = ?', (user_id,)).fetchone()[0]
    
    conn.close()
    
    # Simple pagination
    total_pages = (total_cards + per_page - 1) // per_page
    pagination = {
        'page': page,
        'pages': total_pages,
        'has_prev': page > 1,
        'has_next': page < total_pages,
        'prev_num': page - 1 if page > 1 else None,
        'next_num': page + 1 if page < total_pages else None
    }
    
    return render_template('index.html', 
                         cards=cards, 
                         stats=stats, 
                         pagination=pagination,
                         current_filters={},
                         active_updates=active_updates,
                         progress_state=progress_state)

@app.route('/add_card', methods=['GET', 'POST'])
@login_required
def add_card():
    if request.method == 'POST':
        try:
            # Get all form data
            card_name = request.form.get('card_name', '').strip()
            set_name = request.form.get('set_name', '').strip()
            set_code = request.form.get('set_code', '').strip()
            collector_number = request.form.get('collector_number', '').strip()
            quantity = int(request.form.get('quantity', 1))
            condition = request.form.get('condition', 'Near Mint')
            purchase_price = float(request.form.get('purchase_price', 0))
            is_foil = bool(request.form.get('is_foil'))
            
            if not card_name:
                flash('Card name is required')
                return render_template('add_card.html')
            
            conn = inventory_app.get_db_connection()
            
            # Check if card already exists for this user
            existing_card = conn.execute('''
                SELECT id, quantity FROM cards 
                WHERE user_id = ? AND card_name = ? AND set_code = ? 
                AND collector_number = ? AND is_foil = ? AND condition = ?
            ''', (get_current_user_id(), card_name, set_code, collector_number, is_foil, condition)).fetchone()
            
            if existing_card:
                # Update quantity instead of creating duplicate
                new_quantity = existing_card['quantity'] + quantity
                conn.execute('''
                    UPDATE cards SET quantity = ?, last_updated = ?
                    WHERE id = ?
                ''', (new_quantity, datetime.now().isoformat(), existing_card['id']))
                conn.commit()
                conn.close()
                
                flash(f'Updated {card_name} quantity to {new_quantity} (added {quantity})')
                return redirect(url_for('index'))
            
            # Insert new card
            cursor = conn.execute('''
                INSERT INTO cards (
                    card_name, set_name, set_code, collector_number, quantity, 
                    is_foil, condition, purchase_price, current_price, price_change, 
                    total_value, user_id, last_updated
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                card_name, set_name, set_code, collector_number, quantity,
                is_foil, condition, purchase_price, 0.0, 0.0, 0.0,
                get_current_user_id(), datetime.now().isoformat()
            ))
            
            card_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            # Auto-fetch card data from Scryfall in background
            def fetch_card_data_background():
                try:
                    card_data = fetch_scryfall_data_standalone(card_name, set_code, collector_number)
                    if card_data:
                        current_price = float(card_data.get('usd_foil' if is_foil else 'usd', 0) or 0)
                        total_value = current_price * quantity
                        price_change = current_price - purchase_price
                        
                        conn = inventory_app.get_db_connection()
                        conn.execute('''
                            UPDATE cards 
                            SET current_price = ?, total_value = ?, price_change = ?, 
                                market_url = ?, image_url = ?, image_url_back = ?, 
                                rarity = ?, colors = ?, mana_cost = ?, mana_value = ?, 
                                card_type = ?, last_updated = ?
                            WHERE id = ?
                        ''', (
                            current_price, total_value, price_change,
                            card_data.get('market_url', ''), card_data.get('image_url', ''),
                            card_data.get('image_url_back', ''), card_data.get('rarity', ''),
                            card_data.get('colors', ''), card_data.get('mana_cost', ''),
                            card_data.get('mana_value', 0), card_data.get('card_type', ''),
                            datetime.now().isoformat(), card_id
                        ))
                        conn.commit()
                        conn.close()
                        logger.info(f"Auto-updated card data for: {card_name}")
                except Exception as e:
                    logger.error(f"Background card data fetch failed for {card_name}: {e}")
            
            # Start background data fetch
            threading.Thread(target=fetch_card_data_background, daemon=True).start()
            
            flash(f'Added {card_name} to your collection (fetching prices and images...)')
            return redirect(url_for('index'))
            
        except ValueError as e:
            flash(f'Invalid input: {e}')
            return render_template('add_card.html')
        except Exception as e:
            logger.error(f"Error adding card: {e}")
            flash('Error adding card to collection')
            return render_template('add_card.html')
    
    return render_template('add_card.html')

@app.route('/collections')
@login_required  
def collections():
    return render_template('collections.html', templates=[], user_collections=[])

@app.route('/alerts')
@login_required
def alerts():
    return render_template('alerts.html', alerts=[])

@app.route('/import_csv', methods=['POST'])
@login_required
def import_csv():
    """Import CSV file to database with background processing and progress tracking"""
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
            from csv_import_helpers import preprocess_csv_data, import_cards_with_progress, update_card_prices_and_metadata_with_progress
            
            # Initialize progress
            progress_state[user_id] = {
                'type': 'start',
                'total': len(dataframe),
                'message': f'Starting import of {len(dataframe)} cards...',
                'phase': 'preprocessing'
            }
            
            # Process CSV data
            df_processed = preprocess_csv_data(dataframe, user_id)
            
            # Import cards with progress tracking
            imported_count, imported_card_ids = import_cards_with_progress(df_processed, user_id, progress_state)
            
            # Auto-update prices and metadata
            updated_count = 0
            if imported_card_ids:
                progress_state[user_id] = {
                    'type': 'progress',
                    'message': f'Fetching prices and images for {len(imported_card_ids)} cards...',
                    'phase': 'price_update',
                    'current': 0,
                    'total': len(imported_card_ids)
                }
                
                updated_count = update_card_prices_and_metadata_with_progress(imported_card_ids, user_id, progress_state)
            
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

@app.route('/progress_status')
@login_required 
def progress_status():
    """Get current progress status for the user"""
    user_id = get_current_user_id()
    
    # Check if there's an active operation
    is_active = active_updates.get(user_id, False)
    latest_progress = progress_state.get(user_id, None)
    
    response = {
        'active': is_active,
        'latest_progress': latest_progress
    }
    
    return jsonify(response)

@app.route('/update_prices')
@login_required
def update_prices():
    """Update prices for first 100 cards (test function)"""
    user_id = get_current_user_id()
    
    # Get first 100 cards for this user
    conn = inventory_app.get_db_connection()
    cards = conn.execute('SELECT id FROM cards WHERE user_id = ? LIMIT 100', (user_id,)).fetchall()
    conn.close()
    
    if not cards:
        flash('No cards to update')
        return redirect(url_for('index'))
    
    card_ids = [card['id'] for card in cards]
    
    # Start background update
    def background_price_update():
        try:
            from csv_import_helpers import update_card_prices_and_metadata_with_progress
            progress_state[user_id] = {
                'type': 'start',
                'message': f'Starting price update for {len(card_ids)} cards...',
                'total': len(card_ids),
                'current': 0
            }
            active_updates[user_id] = True
            
            updated_count = update_card_prices_and_metadata_with_progress(card_ids, user_id, progress_state)
            
            progress_state[user_id] = {
                'type': 'complete',
                'message': f'Successfully updated {updated_count} cards',
                'updated_count': updated_count,
                'total': len(card_ids)
            }
            active_updates[user_id] = False
            
        except Exception as e:
            logger.error(f"Price update error: {e}")
            progress_state[user_id] = {
                'type': 'error',
                'message': f'Update failed: {str(e)}',
                'error': str(e)
            }
            active_updates[user_id] = False
    
    active_updates[user_id] = True
    threading.Thread(target=background_price_update, daemon=True).start()
    
    flash('Price update started! Progress will be shown below.')
    return redirect(url_for('index'))

@app.route('/update_all_prices')
@login_required
def update_all_prices():
    """Update prices for all cards (background function)"""
    user_id = get_current_user_id()
    
    # Get all cards for this user
    conn = inventory_app.get_db_connection()
    cards = conn.execute('SELECT id FROM cards WHERE user_id = ?', (user_id,)).fetchall()
    conn.close()
    
    if not cards:
        flash('No cards to update')
        return redirect(url_for('index'))
    
    card_ids = [card['id'] for card in cards]
    
    # Start background update
    def background_price_update_all():
        try:
            from csv_import_helpers import update_card_prices_and_metadata_with_progress
            progress_state[user_id] = {
                'type': 'start',
                'message': f'Starting price update for all {len(card_ids)} cards...',
                'total': len(card_ids),
                'current': 0
            }
            active_updates[user_id] = True
            
            updated_count = update_card_prices_and_metadata_with_progress(card_ids, user_id, progress_state)
            
            progress_state[user_id] = {
                'type': 'complete',
                'message': f'Successfully updated {updated_count} cards',
                'updated_count': updated_count,
                'total': len(card_ids)
            }
            active_updates[user_id] = False
            
        except Exception as e:
            logger.error(f"Price update error: {e}")
            progress_state[user_id] = {
                'type': 'error',
                'message': f'Update failed: {str(e)}',
                'error': str(e)
            }
            active_updates[user_id] = False
    
    active_updates[user_id] = True
    threading.Thread(target=background_price_update_all, daemon=True).start()
    
    flash('Background price update started for all cards! Progress will be shown below.')
    return redirect(url_for('index'))

@app.route('/card_detail/<int:card_id>')
@login_required
def card_detail(card_id):
    """View/edit individual card details"""
    conn = inventory_app.get_db_connection()
    card = conn.execute('SELECT * FROM cards WHERE id = ? AND user_id = ?', 
                       (card_id, get_current_user_id())).fetchone()
    conn.close()
    
    if not card:
        flash('Card not found')
        return redirect(url_for('index'))
    
    return render_template('card_detail.html', card=card)

@app.route('/edit_card/<int:card_id>', methods=['POST'])
@login_required
def edit_card(card_id):
    """Edit card details"""
    conn = inventory_app.get_db_connection()
    
    # Verify card belongs to user
    card = conn.execute('SELECT * FROM cards WHERE id = ? AND user_id = ?', 
                       (card_id, get_current_user_id())).fetchone()
    if not card:
        conn.close()
        flash('Card not found')
        return redirect(url_for('index'))
    
    # Update card
    card_name = request.form.get('card_name')
    set_name = request.form.get('set_name', '')
    quantity = int(request.form.get('quantity', 1))
    condition = request.form.get('condition', 'Near Mint')
    purchase_price = float(request.form.get('purchase_price', 0))
    
    conn.execute('''
        UPDATE cards 
        SET card_name = ?, set_name = ?, quantity = ?, condition = ?, purchase_price = ?
        WHERE id = ?
    ''', (card_name, set_name, quantity, condition, purchase_price, card_id))
    
    conn.commit()
    conn.close()
    
    flash('Card updated successfully')
    return redirect(url_for('card_detail', card_id=card_id))

@app.route('/delete_card/<int:card_id>', methods=['POST'])
@login_required
def delete_card(card_id):
    """Delete a card"""
    conn = inventory_app.get_db_connection()
    
    # Verify card belongs to user
    card = conn.execute('SELECT * FROM cards WHERE id = ? AND user_id = ?', 
                       (card_id, get_current_user_id())).fetchone()
    if not card:
        conn.close()
        flash('Card not found')
        return redirect(url_for('index'))
    
    conn.execute('DELETE FROM cards WHERE id = ?', (card_id,))
    conn.commit()
    conn.close()
    
    flash('Card deleted successfully')
    return redirect(url_for('index'))

@app.route('/mark_alert_read/<int:alert_id>')
@login_required
def mark_alert_read(alert_id):
    """Mark price alert as read"""
    # For now, just redirect back since we don't have alerts implemented
    flash('Alert marked as read')
    return redirect(url_for('alerts'))

@app.route('/api/search_cards')
@login_required
def search_cards():
    """Search for cards using Scryfall API with autocomplete suggestions"""
    query = request.args.get('q', '').strip()
    
    if len(query) < 2:
        return jsonify([])
    
    try:
        import requests
        import time
        from difflib import SequenceMatcher
        
        # Search Scryfall API
        search_url = f'https://api.scryfall.com/cards/search'
        params = {
            'q': f'!"{query}" OR "{query}"',  # Exact match first, then fuzzy
            'order': 'name',
            'unique': 'prints'
        }
        
        response = requests.get(search_url, params=params, timeout=5)
        time.sleep(0.05)  # Respect rate limits
        
        results = []
        if response.status_code == 200:
            data = response.json()
            cards = data.get('data', [])
            
            # Sort by relevance using fuzzy matching
            def relevance_score(card):
                name = card.get('name', '').lower()
                query_lower = query.lower()
                
                # Exact match gets highest score
                if query_lower == name:
                    return 1.0
                # Starts with query gets high score
                elif name.startswith(query_lower):
                    return 0.9
                # Contains query gets medium score
                elif query_lower in name:
                    return 0.7
                # Fuzzy match gets lower score
                else:
                    return SequenceMatcher(None, query_lower, name).ratio()
            
            # Sort by relevance and limit to top 10
            sorted_cards = sorted(cards, key=relevance_score, reverse=True)[:10]
            
            for card in sorted_cards:
                # Handle image URLs for double-faced cards
                image_url = ''
                if 'image_uris' in card:
                    image_url = card['image_uris'].get('small', '')
                elif 'card_faces' in card and len(card['card_faces']) > 0:
                    first_face = card['card_faces'][0]
                    if 'image_uris' in first_face:
                        image_url = first_face['image_uris'].get('small', '')
                
                result = {
                    'name': card.get('name', ''),
                    'set_name': card.get('set_name', ''),
                    'set': card.get('set', '').upper(),
                    'collector_number': card.get('collector_number', ''),
                    'rarity': card.get('rarity', '').title(),
                    'mana_cost': card.get('mana_cost', ''),
                    'type_line': card.get('type_line', ''),
                    'colors': ','.join(card.get('colors', [])),
                    'image_url': image_url,
                    'prices': {
                        'usd': card.get('prices', {}).get('usd'),
                        'usd_foil': card.get('prices', {}).get('usd_foil')
                    }
                }
                
                # Handle double-faced cards for mana cost and type
                if 'card_faces' in card and len(card['card_faces']) > 0:
                    first_face = card['card_faces'][0]
                    if not result['mana_cost'] and 'mana_cost' in first_face:
                        result['mana_cost'] = first_face.get('mana_cost', '')
                    if not result['type_line'] and 'type_line' in first_face:
                        result['type_line'] = first_face.get('type_line', '')
                
                results.append(result)
        
        return jsonify(results)
        
    except Exception as e:
        logger.error(f"Card search error: {e}")
        return jsonify([])

@app.route('/delete_all_cards', methods=['POST'])
@login_required
def delete_all_cards():
    """Delete all cards for the current user"""
    try:
        user_id = get_current_user_id()
        conn = inventory_app.get_db_connection()
        
        # Get count before deletion
        count_result = conn.execute('SELECT COUNT(*) FROM cards WHERE user_id = ?', (user_id,)).fetchone()
        total_cards = count_result[0]
        
        if total_cards == 0:
            conn.close()
            return jsonify({'success': False, 'error': 'No cards to delete'})
        
        # Delete all cards for this user
        conn.execute('DELETE FROM cards WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True, 
            'message': f'Successfully deleted {total_cards} cards from your collection',
            'deleted_count': total_cards
        })
        
    except Exception as e:
        logger.error(f"Error deleting all cards: {e}")
        return jsonify({'success': False, 'error': 'Failed to delete cards'})

@app.route('/mass_delete', methods=['POST'])
@login_required
def mass_delete():
    """Delete selected cards"""
    try:
        data = request.json
        card_ids = data.get('card_ids', [])
        
        if not card_ids:
            return jsonify({'success': False, 'error': 'No cards selected'})
        
        user_id = get_current_user_id()
        conn = inventory_app.get_db_connection()
        
        # Verify all cards belong to this user
        placeholders = ','.join(['?' for _ in card_ids])
        params = card_ids + [user_id]
        
        verified_cards = conn.execute(f'''
            SELECT id FROM cards 
            WHERE id IN ({placeholders}) AND user_id = ?
        ''', params).fetchall()
        
        verified_ids = [card['id'] for card in verified_cards]
        
        if not verified_ids:
            conn.close()
            return jsonify({'success': False, 'error': 'No valid cards found to delete'})
        
        # Delete the verified cards
        conn.execute(f'''
            DELETE FROM cards WHERE id IN ({','.join(['?' for _ in verified_ids])})
        ''', verified_ids)
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'deleted_count': len(verified_ids),
            'message': f'Successfully deleted {len(verified_ids)} cards'
        })
        
    except Exception as e:
        logger.error(f"Error in mass delete: {e}")
        return jsonify({'success': False, 'error': 'Failed to delete cards'})

@app.route('/mass_update_prices', methods=['POST'])
@login_required
def mass_update_prices():
    """Update prices for selected cards"""
    try:
        data = request.json
        card_ids = data.get('card_ids', [])
        
        if not card_ids:
            return jsonify({'success': False, 'error': 'No cards selected'})
        
        user_id = get_current_user_id()
        
        # Start background update
        def background_mass_update():
            try:
                from csv_import_helpers import update_card_prices_and_metadata_with_progress
                progress_state[user_id] = {
                    'type': 'start',
                    'message': f'Starting price update for {len(card_ids)} selected cards...',
                    'total': len(card_ids),
                    'current': 0
                }
                active_updates[user_id] = True
                
                updated_count = update_card_prices_and_metadata_with_progress(card_ids, user_id, progress_state)
                
                progress_state[user_id] = {
                    'type': 'complete',
                    'message': f'Successfully updated {updated_count} selected cards',
                    'updated_count': updated_count,
                    'total': len(card_ids)
                }
                active_updates[user_id] = False
                
            except Exception as e:
                logger.error(f"Mass price update error: {e}")
                progress_state[user_id] = {
                    'type': 'error',
                    'message': f'Update failed: {str(e)}',
                    'error': str(e)
                }
                active_updates[user_id] = False
        
        active_updates[user_id] = True
        threading.Thread(target=background_mass_update, daemon=True).start()
        
        return jsonify({
            'success': True,
            'message': f'Started price update for {len(card_ids)} cards'
        })
        
    except Exception as e:
        logger.error(f"Error starting mass update: {e}")
        return jsonify({'success': False, 'error': 'Failed to start price update'})

@app.route('/api/cards')
@login_required
def api_cards():
    """API endpoint for cards data"""
    user_id = get_current_user_id()
    conn = inventory_app.get_db_connection()
    
    cards = conn.execute('''
        SELECT id, card_name, set_name, current_price, total_value, price_change 
        FROM cards WHERE user_id = ?
        ORDER BY total_value DESC
    ''', (user_id,)).fetchall()
    
    conn.close()
    
    # Convert to list of dicts
    cards_data = []
    for card in cards:
        cards_data.append({
            'id': card['id'],
            'card_name': card['card_name'],
            'set_name': card['set_name'],
            'current_price': card['current_price'] or 0,
            'total_value': card['total_value'] or 0,
            'price_change': card['price_change'] or 0
        })
    
    return jsonify(cards_data)

@app.route('/api/card/<int:card_id>/image')
@login_required
def api_card_image(card_id):
    """API endpoint for card image"""
    user_id = get_current_user_id()
    conn = inventory_app.get_db_connection()
    
    card = conn.execute('''
        SELECT image_url FROM cards 
        WHERE id = ? AND user_id = ?
    ''', (card_id, user_id)).fetchone()
    
    conn.close()
    
    if card and card['image_url']:
        return jsonify({'image_url': card['image_url']})
    else:
        return jsonify({'image_url': None})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)