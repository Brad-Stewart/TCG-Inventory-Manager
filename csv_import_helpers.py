import pandas as pd
import sqlite3
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def preprocess_csv_data(df, user_id):
    """Preprocess CSV data with column mapping"""
    # Log all columns for debugging
    logger.info(f"Original CSV columns: {list(df.columns)}")
    
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
    column_mapping = {}
    for original_col, target_col in manabox_mapping.items():
        if original_col in df.columns:
            column_mapping[original_col] = target_col
    
    # Apply column mapping
    df = df.rename(columns=column_mapping)
    
    # Fill missing required columns
    if 'card_name' not in df.columns:
        # Try to find the first column that might be card names
        for col in df.columns:
            if df[col].dtype == 'object':  # String column
                df['card_name'] = df[col]
                break
        else:
            raise ValueError(f'Could not identify card name column')
    
    # Set defaults for missing columns
    df['set_name'] = df.get('set_name', '')
    df['set_code'] = df.get('set_code', '')
    df['collector_number'] = df.get('collector_number', '')
    df['quantity'] = df.get('quantity', 1)
    df['is_foil'] = df.get('is_foil', False)
    df['condition'] = df.get('condition', 'Near Mint')
    df['language'] = df.get('language', 'English')
    df['purchase_price'] = df.get('purchase_price', 0)
    
    # Handle rarity from Manabox CSV if available
    if 'Rarity' in df.columns:
        df['rarity'] = df['Rarity'].str.title()
    else:
        df['rarity'] = ''
    
    return df

def import_cards_with_progress(df, user_id, progress_state):
    """Import cards to database with progress tracking"""
    try:
        from working_app import inventory_app
    except ImportError:
        from app import inventory_app
    
    conn = inventory_app.get_db_connection()
    imported_count = 0
    error_count = 0
    imported_card_ids = []
    total_cards = len(df)
    
    for idx, row in df.iterrows():
        try:
            # Update progress every 10 cards
            if idx % 10 == 0:
                progress_state[user_id] = {
                    'type': 'progress',
                    'current': idx + 1,
                    'total': total_cards,
                    'message': f'Importing card {idx + 1} of {total_cards}...',
                    'phase': 'import',
                    'card_name': str(row.get('card_name', ''))[:50]
                }
            
            # Handle foil field (Manabox uses "foil"/"normal")
            is_foil = False
            if 'is_foil' in row and pd.notna(row['is_foil']):
                foil_value = str(row['is_foil']).lower().strip()
                is_foil = foil_value in ['foil', 'true', 'yes', '1']
            
            # Get card name and validate
            card_name = str(row['card_name']).strip() if pd.notna(row['card_name']) else ''
            if not card_name or card_name == 'nan':
                error_count += 1
                continue
            
            # Prepare data with safe conversions
            set_name = str(row['set_name']).strip() if pd.notna(row['set_name']) else ''
            set_code = str(row['set_code']).strip() if pd.notna(row['set_code']) else ''
            collector_number = str(row['collector_number']).strip() if pd.notna(row['collector_number']) else ''
            
            condition_raw = str(row['condition']).strip() if pd.notna(row['condition']) else 'near_mint'
            condition = condition_raw.replace('_', ' ').title()
            
            language_raw = str(row['language']).strip() if pd.notna(row['language']) else 'en'
            language = 'English' if language_raw == 'en' else language_raw
            
            rarity = str(row.get('rarity', '')).strip() if pd.notna(row.get('rarity', '')) else ''
            
            try:
                quantity = int(row['quantity']) if pd.notna(row['quantity']) else 1
            except (ValueError, TypeError):
                quantity = 1
            
            try:
                purchase_price = float(row['purchase_price']) if pd.notna(row['purchase_price']) else 0
            except (ValueError, TypeError, AttributeError):
                purchase_price = 0
            
            cursor = conn.execute('''
                INSERT OR REPLACE INTO cards 
                (card_name, set_name, set_code, collector_number, quantity, is_foil, 
                 condition, language, purchase_price, current_price, price_change, 
                 total_value, rarity, image_url_back, user_id, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                card_name, set_name, set_code, collector_number, quantity, is_foil,
                condition, language, purchase_price, 0.0, 0.0, 0.0, rarity, '', 
                user_id, datetime.now().isoformat()
            ))
            imported_card_ids.append(cursor.lastrowid)
            imported_count += 1
            
        except Exception as e:
            error_count += 1
            logger.error(f"Could not import row {idx}: {e}")
    
    conn.commit()
    conn.close()
    
    return imported_count, imported_card_ids

def update_card_prices_and_metadata_with_progress(card_ids, user_id, progress_state):
    """Update prices and metadata with progress tracking"""
    try:
        from working_app import inventory_app, fetch_scryfall_data_standalone
    except ImportError:
        from app import inventory_app, fetch_scryfall_data_standalone
    
    if not card_ids:
        return 0
    
    conn = inventory_app.get_db_connection()
    updated_count = 0
    
    # Get cards by IDs
    placeholders = ','.join(['?' for _ in card_ids])
    cards = conn.execute(f'SELECT * FROM cards WHERE id IN ({placeholders})', card_ids).fetchall()
    
    for i, card in enumerate(cards):
        try:
            # Update progress
            progress_state[user_id] = {
                'type': 'progress',
                'current': i + 1,
                'total': len(cards),
                'message': f'Fetching price for {card["card_name"]}...',
                'phase': 'price_update',
                'card_name': card['card_name']
            }
            
            card_data = fetch_scryfall_data_standalone(
                card['card_name'], 
                card['set_code'], 
                card['collector_number'] if card['collector_number'] else None
            )
            
            current_price = float(card_data.get('usd_foil' if card['is_foil'] else 'usd', 0) or 0)
            total_value = current_price * card['quantity']
            price_change = current_price - (card['purchase_price'] or 0)
            
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
            
            # Commit every 10 cards
            if (i + 1) % 10 == 0:
                conn.commit()
                
        except Exception as e:
            logger.error(f"Could not update metadata for {card['card_name']}: {e}")
    
    conn.commit()
    conn.close()
    return updated_count