import sqlite3
import requests
import json
import time

def update_sephiroth_cards():
    """Update Sephiroth cards with correct image URLs"""
    
    # Get the correct data from Scryfall
    print("Fetching correct data from Scryfall...")
    base_url = "https://api.scryfall.com/cards/named"
    params = {
        'fuzzy': "Sephiroth, Fabled SOLDIER",
        'format': 'json'
    }
    
    response = requests.get(base_url, params=params)
    if response.status_code != 200:
        print(f"Failed to fetch data: {response.status_code}")
        return
    
    data = response.json()
    
    # Extract the image URL using our logic
    image_url = ''
    if 'image_uris' in data:
        image_url = data['image_uris'].get('normal', '')
    elif 'card_faces' in data and len(data['card_faces']) > 0:
        first_face = data['card_faces'][0]
        if 'image_uris' in first_face:
            image_url = first_face['image_uris'].get('normal', '')
    
    print(f"Found image URL: {image_url}")
    
    if not image_url:
        print("No image URL found!")
        return
    
    # Update database
    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()
    
    # Update all Sephiroth cards
    cursor.execute('''
        UPDATE cards 
        SET image_url = ?, 
            market_url = ?,
            rarity = ?,
            mana_cost = ?,
            card_type = ?,
            last_updated = CURRENT_TIMESTAMP
        WHERE card_name LIKE "%Sephiroth%"
    ''', (
        image_url,
        data.get('purchase_uris', {}).get('tcgplayer', ''),
        data.get('rarity', '').title(),
        data['card_faces'][0].get('mana_cost', '') if 'card_faces' in data else data.get('mana_cost', ''),
        data['card_faces'][0].get('type_line', '') if 'card_faces' in data else data.get('type_line', '')
    ))
    
    affected_rows = cursor.rowcount
    conn.commit()
    conn.close()
    
    print(f"Updated {affected_rows} Sephiroth cards with correct image URL")

if __name__ == "__main__":
    update_sephiroth_cards()