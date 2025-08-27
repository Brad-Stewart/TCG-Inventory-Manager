import sqlite3
import re

def format_colors_wubrg(colors_string):
    """
    Convert colors from comma-separated format to WUBRG order without commas.
    Examples:
    - "B,G" -> "BG"
    - "B,G,R,U,W" -> "WUBRG" 
    - "B,R" -> "BR"
    - "G,W" -> "WG"
    - "R,U,W" -> "WUR"
    """
    if not colors_string or colors_string.strip() == '':
        return ''
    
    # Parse colors from comma-separated string
    colors = [c.strip() for c in colors_string.split(',')]
    
    # WUBRG order
    wubrg_order = ['W', 'U', 'B', 'R', 'G']
    
    # Filter and sort colors according to WUBRG order
    ordered_colors = [color for color in wubrg_order if color in colors]
    
    return ''.join(ordered_colors)

def update_color_display():
    """Update color display format in database"""
    conn = sqlite3.connect('../inventory.db')
    cursor = conn.cursor()
    
    # Get all cards with colors
    cursor.execute('SELECT id, card_name, colors FROM cards WHERE colors IS NOT NULL AND colors != ""')
    cards = cursor.fetchall()
    
    print(f"Found {len(cards)} cards with colors to reformat...")
    
    updated_count = 0
    for card in cards:
        card_id, card_name, current_colors = card
        
        # Format for proper WUBRG display
        clean_colors = format_colors_wubrg(current_colors)
        
        # Only update if different
        if current_colors != clean_colors:
            cursor.execute('UPDATE cards SET colors = ? WHERE id = ?', (clean_colors, card_id))
            print(f"Updated {card_name}: '{current_colors}' -> '{clean_colors}'")
            updated_count += 1
    
    conn.commit()
    conn.close()
    
    print(f"\nUpdated {updated_count} cards with proper WUBRG color format!")

def test_color_formatting():
    """Test the color formatting function"""
    test_cases = [
        ('B,G', 'BG'),
        ('B,G,R,U,W', 'WUBRG'),
        ('G,W', 'WG'),
        ('R,U,W', 'WUR'),
        ('B,R', 'BR'),
        ('B,U', 'UB'),
        ('G,R', 'RG'),
        ('B', 'B'),
        ('W', 'W'),
        ('', ''),
        ('G,R,U', 'URG'),
        ('B,W', 'WB'),
    ]
    
    print("Testing color formatting:")
    for original, expected in test_cases:
        result = format_colors_wubrg(original)
        status = "✓" if result == expected else "✗"
        print(f"{status} '{original}' -> '{result}' (expected '{expected}')")

if __name__ == '__main__':
    # Run tests first
    test_color_formatting()
    print("\n" + "="*50)
    
    # Update database
    update_color_display()