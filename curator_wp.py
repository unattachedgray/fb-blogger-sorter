import urllib.request
import urllib.error
import json
import base64
import ssl
import os
import mimetypes
import curator_config as cfg
import curator_data as data_mod
import curator_ai as ai_mod
from datetime import datetime

def wp_api_call(endpoint, method="GET", data=None, creds=None):
    if not creds: creds = cfg.load_credentials()
    url = f"{creds.get('wp_url')}/wp-json/wp/v2/{endpoint}"
    auth_str = f"{creds.get('wp_user')}:{creds.get('wp_pass')}"
    auth_b64 = base64.b64encode(auth_str.encode()).decode()
    
    headers = {
        "Authorization": f"Basic {auth_b64}",
        "Content-Type": "application/json"
    }
    
    print(f"[WP] Request: {method} {url}")
    
    req = urllib.request.Request(url, method=method, headers=headers)
    if data: req.data = json.dumps(data).encode('utf-8')
    
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as res:
            print(f"[WP] Response: {res.status}")
            return json.loads(res.read()), res.headers
    except Exception as e:
        print(f"[WP] Error: {e}")
        return {"error": str(e)}, {}

def upload_media(filepath, wp_url, auth_header):
    try:
        mime, _ = mimetypes.guess_type(filepath)
        if not mime: mime = 'application/octet-stream'
        with open(filepath, 'rb') as f: file_data = f.read()
        
        req = urllib.request.Request(f"{wp_url}/wp-json/wp/v2/media", data=file_data)
        req.add_header("Authorization", auth_header)
        req.add_header("Content-Type", mime)
        req.add_header("Content-Disposition", f'attachment; filename="{os.path.basename(filepath)}"')
        
        ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, context=ctx, timeout=60) as res:
            d = json.loads(res.read())
            return d.get('id'), d.get('source_url')
    except: return None, None

def process_single_post_upload(post_idx, wp_url, wp_user, wp_pass, force_today, use_ai, gemini_key, c_title, c_content, c_cat, all_posts_ref):
    post = all_posts_ref[int(post_idx)]
    auth_str = f"{wp_user}:{wp_pass}"
    auth_b64 = base64.b64encode(auth_str.encode()).decode()
    auth_header = f"Basic {auth_b64}"

    date_str, dt_obj = data_mod.extract_date(post)
    iso_date = datetime.now().isoformat() if force_today else (dt_obj.isoformat() if dt_obj else datetime.now().isoformat())

    final_title = c_title
    content_html = c_content
    
    if not final_title:
        text, raw_t = data_mod.extract_content(post)
        final_title = raw_t if raw_t else date_str
        if use_ai and gemini_key:
             ai_res = ai_mod.call_gemini_ai(text, [], gemini_key, [])
             final_title = ai_res[0]
    
    if not content_html:
        # Construct HTML from attachments
        text, _ = data_mod.extract_content(post)
        media_top = ""
        media_bot = ""
        count = 0
        for att in post.get('attachments', []):
             for d in att.get('data', []):
                 if 'media' in d:
                     uri = d['media'].get('uri', '')
                     path = os.path.join(cfg.EXPORT_FOLDER_PATH, uri)
                     if os.path.exists(path):
                         mid, murl = upload_media(path, wp_url, auth_header)
                         if mid:
                             tag = f'<img src="{murl}" class="wp-image-{mid}"/>'
                             if count < 5: media_top += tag
                             else: media_bot += tag
                             count += 1
        content_html = media_top + f"<p>{text}</p>" + media_bot

    wp_payload = {
        'title': final_title,
        'content': content_html,
        'status': 'publish',
        'date': iso_date
    }
    if c_cat: wp_payload['categories'] = [int(c_cat)]

    res, _ = wp_api_call("posts", "POST", wp_payload)
    
    if 'id' in res:
        return True, {'id': res['id'], 'link': res.get('link'), 'imgs': 0, 'vids': 0}
    return False, str(res)