import os
import json

EXPORT_FOLDER_PATH = r'D:\temp\fb-blogger-sorter\facebook-data' 
POSTS_PER_PAGE = 50
PORT = 8000
PROCESSED_FILE = "processed_posts.json"
CREDENTIALS_FILE = "credentials.json"
IMPORTED_MEDIA_DIR = "imported_media"
LEARNING_FILE = "ai_learning.json"

def load_credentials():
    if os.path.exists(CREDENTIALS_FILE):
        try:
            with open(CREDENTIALS_FILE, 'r', encoding='utf-8') as f: return json.load(f)
        except Exception as e:
            print(f"Error loading credentials: {e}")
            pass
    return {}