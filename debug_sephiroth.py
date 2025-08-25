import requests
import json
import time

def test_sephiroth_api():
    """Test Scryfall API response for Sephiroth card"""
    
    # Test the fuzzy search
    card_name = "Sephiroth, Fabled SOLDIER // Sephiroth, One-Winged Angel"
    print(f"Testing card: {card_name}")
    
    # Try fuzzy search
    print("\n=== Fuzzy Search ===")
    base_url = "https://api.scryfall.com/cards/named"
    params = {
        'fuzzy': card_name,
        'format': 'json'
    }
    
    response = requests.get(base_url, params=params)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Card Name: {data.get('name', 'N/A')}")
        print(f"Has image_uris: {'image_uris' in data}")
        print(f"Has card_faces: {'card_faces' in data}")
        
        if 'image_uris' in data:
            print(f"Direct image URL: {data['image_uris'].get('normal', 'No normal image')}")
        
        if 'card_faces' in data:
            print(f"Number of faces: {len(data['card_faces'])}")
            for i, face in enumerate(data['card_faces']):
                print(f"Face {i+1}: {face.get('name', 'N/A')}")
                if 'image_uris' in face:
                    print(f"  Face {i+1} image URL: {face['image_uris'].get('normal', 'No normal image')}")
                else:
                    print(f"  Face {i+1} has no image_uris")
        
        # Save full response for inspection
        with open('sephiroth_response.json', 'w') as f:
            json.dump(data, f, indent=2)
        print("\nFull response saved to sephiroth_response.json")
        
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
    
    time.sleep(0.1)
    
    # Also try with just the first name
    print("\n=== First Name Only ===")
    params['fuzzy'] = "Sephiroth, Fabled SOLDIER"
    response = requests.get(base_url, params=params)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Card Name: {data.get('name', 'N/A')}")
        print(f"Has image_uris: {'image_uris' in data}")
        print(f"Has card_faces: {'card_faces' in data}")

if __name__ == "__main__":
    test_sephiroth_api()