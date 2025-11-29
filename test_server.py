import urllib.request
import json

def test_server():
    print("Testing Server...")
    
    # Test Root
    try:
        with urllib.request.urlopen('http://localhost:8000/') as response:
            html = response.read().decode('utf-8')
            print(f"Root Status: {response.status}")
            if "<!DOCTYPE html>" in html or "<html" in html:
                print("Root Content: HTML detected (PASS)")
            elif "Directory listing" in html:
                print("Root Content: Directory listing detected (FAIL)")
            else:
                print(f"Root Content: Unknown ({html[:100]}...)")
    except Exception as e:
        print(f"Root Error: {e}")

    # Test API
    try:
        with urllib.request.urlopen('http://localhost:8000/api_wp_list') as response:
            data = json.loads(response.read().decode('utf-8'))
            print(f"API Status: {response.status}")
            if 'posts' in data:
                print("API Content: JSON detected (PASS)")
            else:
                print(f"API Content: Invalid JSON ({data})")
    except Exception as e:
        print(f"API Error: {e}")

if __name__ == "__main__":
    test_server()
