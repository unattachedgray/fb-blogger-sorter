from bs4 import BeautifulSoup
import os

def test_html_structure():
    """Test that index.html has the required structure"""
    
    # Read HTML file
    html_path = os.path.join('assets', 'index.html')
    with open(html_path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    soup = BeautifulSoup(html, 'html.parser')
    
    tests_passed = 0
    tests_failed = 0
    
    # Test 1: Body tag exists
    body = soup.find('body')
    if body:
        print("✓ Body tag exists")
        tests_passed += 1
    else:
        print("✗ Body tag missing")
        tests_failed += 1
        return
    
    # Test 2: Header exists
    header = soup.find(class_='header')
    if header:
        print("✓ Header exists")
        tests_passed += 1
    else:
        print("✗ Header missing")
        tests_failed += 1
    
    # Test 3: Tab bar exists
    tab_bar = soup.find(class_='tab-bar')
    if tab_bar:
        print("✓ Tab bar exists")
        tests_passed += 1
    else:
        print("✗ Tab bar missing")
        tests_failed += 1
    
    # Test 4: Three tabs exist (live, local, enhance)
    tabs = soup.find_all(class_='tab')
    if len(tabs) >= 3:
        print(f"✓ Found {len(tabs)} tabs")
        tests_passed += 1
    else:
        print(f"✗ Only {len(tabs)} tabs found, expected 3+")
        tests_failed += 1
    
    # Test 5: Tab content sections exist
    tab_contents = soup.find_all(class_='tab-content')
    if len(tab_contents) >= 3:
        print(f"✓ Found {len(tab_contents)} tab content sections")
        tests_passed += 1
    else:
        print(f"✗ Only {len(tab_contents)} tab content sections, expected 3+")
        tests_failed += 1
    
    # Test 6: Required IDs for tabs
    required_ids = ['btn-live', 'btn-local', 'btn-enhance', 'live', 'local', 'enhance']
    for req_id in required_ids:
        elem = soup.find(id=req_id)
        if elem:
            print(f"✓ Element #{req_id} exists")
            tests_passed += 1
        else:
            print(f"✗ Element #{req_id} missing")
            tests_failed += 1
    
    # Test 7: Header controls exist
    local_controls = soup.find(id='header-local-controls')
    enhance_controls = soup.find(id='header-enhance-controls')
    if local_controls:
        print("✓ Local controls exist")
        tests_passed += 1
    else:
        print("✗ Local controls missing")
        tests_failed += 1
        
    if enhance_controls:
        print("✓ Enhance controls exist")
        tests_passed += 1
    else:
        print("✗ Enhance controls missing")
        tests_failed += 1
    
    print(f"\n{'='*50}")
    print(f"Tests passed: {tests_passed}")
    print(f"Tests failed: {tests_failed}")
    print(f"{'='*50}")
    
    return tests_failed == 0

if __name__ == "__main__":
    success = test_html_structure()
    exit(0 if success else 1)
