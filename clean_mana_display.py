import sqlite3
import re

def format_mana_cost_for_display(mana_cost):
    """
    Convert mana cost from {2}{W}{W} format to cleaner 2WW format
    Examples:
    - {2}{W}{W} -> 2WW
    - {3}{G} -> 3G
    - {B}{B} -> BB
    - {X}{W}{W} -> XWW
    - {1}{G/U} -> 1G/U (keep hybrid indicators)
    - {W/P} -> W/P (keep Phyrexian indicators)
    """
    if not mana_cost or mana_cost.strip() == '':
        return ''
    
    # Remove all curly braces
    cleaned = re.sub(r'[{}]', '', mana_cost)
    
    return cleaned

def update_mana_cost_display():
    """Update mana cost display format in database"""
    conn = sqlite3.connect('../inventory.db')
    cursor = conn.cursor()
    
    # Get all cards with mana costs
    cursor.execute('SELECT id, card_name, mana_cost FROM cards WHERE mana_cost IS NOT NULL AND mana_cost != ""')
    cards = cursor.fetchall()
    
    print(f"Found {len(cards)} cards with mana costs to clean...")
    
    updated_count = 0
    for card in cards:
        card_id, card_name, current_mana_cost = card
        
        # Format for cleaner display
        clean_mana_cost = format_mana_cost_for_display(current_mana_cost)
        
        # Only update if different
        if current_mana_cost != clean_mana_cost:
            cursor.execute('UPDATE cards SET mana_cost = ? WHERE id = ?', (clean_mana_cost, card_id))
            print(f"Updated {card_name}: '{current_mana_cost}' -> '{clean_mana_cost}'")
            updated_count += 1
    
    conn.commit()
    conn.close()
    
    print(f"\nUpdated {updated_count} cards with cleaner mana cost display!")

def test_mana_cost_formatting():
    """Test the mana cost formatting function"""
    test_cases = [
        ('{2}{W}{W}', '2WW'),
        ('{3}{G}', '3G'),
        ('{B}{B}', 'BB'),
        ('{X}{W}{W}', 'XWW'),
        ('{10}', '10'),
        ('{W}', 'W'),
        ('', ''),
        ('{0}', '0'),
        ('{2/W}', '2/W'),
        ('{W/U}', 'W/U'),
        ('{W/P}', 'W/P'),
        ('{1}{G/U}{R}', '1G/UR'),
    ]
    
    print("Testing mana cost formatting:")
    for original, expected in test_cases:
        result = format_mana_cost_for_display(original)
        status = "✓" if result == expected else "✗"
        print(f"{status} '{original}' -> '{result}' (expected '{expected}')")

if __name__ == '__main__':
    # Run tests first
    test_mana_cost_formatting()
    print("\n" + "="*50)
    
    # Update database
    update_mana_cost_display()