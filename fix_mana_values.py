import sqlite3
import re

def calculate_mana_value(mana_cost):
    """
    Calculate mana value (converted mana cost) from mana cost string.
    Examples:
    - {2}{W}{W} = 4 (2 + 1 + 1)
    - {3}{W} = 4 (3 + 1)  
    - {B}{B} = 2 (1 + 1)
    - {X}{W}{W} = 2 (X doesn't count toward CMC, 0 + 1 + 1)
    - {10} = 10
    """
    if not mana_cost or mana_cost.strip() == '':
        return 0
    
    # Remove any spaces and convert to upper case
    mana_cost = mana_cost.strip().upper()
    
    # Find all mana symbols within curly braces
    mana_symbols = re.findall(r'\{([^}]+)\}', mana_cost)
    
    total_cmc = 0
    
    for symbol in mana_symbols:
        # Handle hybrid mana like {2/W} or {W/U}
        if '/' in symbol:
            # For hybrid mana, take the higher cost (or 1 if both are colors)
            parts = symbol.split('/')
            costs = []
            for part in parts:
                if part.isdigit():
                    costs.append(int(part))
                elif part in ['W', 'U', 'B', 'R', 'G', 'C']:  # Color or colorless
                    costs.append(1)
                elif part == 'P':  # Phyrexian
                    costs.append(1)
            total_cmc += max(costs) if costs else 1
        
        # Handle Phyrexian mana like {W/P}
        elif '/P' in symbol:
            color = symbol.replace('/P', '')
            if color in ['W', 'U', 'B', 'R', 'G']:
                total_cmc += 1
        
        # Handle regular numeric costs
        elif symbol.isdigit():
            total_cmc += int(symbol)
        
        # Handle X, Y, Z (variable costs - count as 0 for CMC)
        elif symbol in ['X', 'Y', 'Z']:
            total_cmc += 0  # X costs don't count toward CMC
        
        # Handle regular color symbols
        elif symbol in ['W', 'U', 'B', 'R', 'G', 'C']:
            total_cmc += 1
        
        # Handle other special symbols (S for snow, etc.)
        elif symbol == 'S':
            total_cmc += 1
            
    return total_cmc

def update_mana_values():
    """Update all mana values in the database based on mana costs"""
    conn = sqlite3.connect('../inventory.db')
    cursor = conn.cursor()
    
    # Get all cards with mana costs
    cursor.execute('SELECT id, card_name, mana_cost, mana_value FROM cards WHERE mana_cost IS NOT NULL AND mana_cost != ""')
    cards = cursor.fetchall()
    
    print(f"Found {len(cards)} cards with mana costs to update...")
    
    updated_count = 0
    for card in cards:
        card_id, card_name, mana_cost, current_mana_value = card
        
        # Calculate correct mana value
        correct_mana_value = calculate_mana_value(mana_cost)
        
        # Only update if different
        if current_mana_value != correct_mana_value:
            cursor.execute('UPDATE cards SET mana_value = ? WHERE id = ?', (correct_mana_value, card_id))
            print(f"Updated {card_name}: '{mana_cost}' -> {correct_mana_value} (was {current_mana_value})")
            updated_count += 1
    
    conn.commit()
    conn.close()
    
    print(f"\nUpdated {updated_count} cards with correct mana values!")

def test_mana_value_calculation():
    """Test the mana value calculation function"""
    test_cases = [
        ('{2}{W}{W}', 4),  # 2 + 1 + 1
        ('{3}{W}', 4),     # 3 + 1
        ('{B}{B}', 2),     # 1 + 1
        ('{X}{W}{W}', 2),  # 0 + 1 + 1
        ('{10}', 10),      # 10
        ('{W}', 1),        # 1
        ('', 0),           # Empty
        ('{0}', 0),        # Zero cost
        ('{2/W}', 2),      # Hybrid mana
        ('{W/U}', 1),      # Color hybrid
        ('{15}', 15),      # High cost
    ]
    
    print("Testing mana value calculations:")
    for mana_cost, expected in test_cases:
        result = calculate_mana_value(mana_cost)
        status = "✓" if result == expected else "✗"
        print(f"{status} '{mana_cost}' -> {result} (expected {expected})")

if __name__ == '__main__':
    # Run tests first
    test_mana_value_calculation()
    print("\n" + "="*50)
    
    # Update database
    update_mana_values()