import os
import json
import re
from datetime import datetime
import urllib.parse
import urllib.request
import ssl
import shutil
import html
import curator_config as cfg

# Global State
queued_indices = set()
processed_indices = set()
global_stats = {"posts": 0, "images": 0, "videos": 0}
all_posts = []

def load_processed_state():
    global processed_indices, global_stats
    if os.path.exists(cfg.PROCESSED_FILE):
        try:
            with open(cfg.PROCESSED_FILE, 'r') as f:
                data = json.load(f)
                processed_indices = set(data.get("processed_ids", []))
                global_stats = data.get("stats", {"posts": 0, "images": 0, "videos": 0})
        except: pass

def save_processed_state():
    with open(cfg.PROCESSED_FILE, 'w') as f:
        json.dump({"processed_ids": list(processed_indices), "stats": global_stats}, f)

def mark_processed(idx):
    processed_indices.add(int(idx))
    save_processed_state()

def load_all_posts():
    global all_posts
    all_posts = []
    json_files = []
    for root, dirs, files in os.walk(cfg.EXPORT_FOLDER_PATH):
        for file in files:
            if file.endswith('.json'):
                if "edits_you_made" in file or "posts_on_other" in file or "autofill" in file: continue
                if ('your_posts' in file or 'posts_' in file) and 'check_ins' in file:
                    json_files.append(os.path.join(root, file))
                elif file == 'your_posts_1.json' or file == 'posts_1.json':
                    json_files.append(os.path.join(root, file))
    json_files.sort()
    for fpath in json_files:
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                items = data if isinstance(data, list) else []
                if isinstance(data, dict):
                    for v in data.values():
                        if isinstance(v, list): items = v; break
                all_posts.extend(items)
        except: pass
    
    def get_ts(p):
        for k in ['timestamp', 'creation_timestamp', 'date']:
            if k in p and p[k]: return p[k]
        return 0
    all_posts.sort(key=get_ts)
    print(f"Loaded {len(all_posts)} posts.")

def fix_encoding(text):
    if not text: return ""
    try: return text.encode('latin1').decode('utf-8')
    except: return text

def extract_content(post):
    content = []
    if 'data' in post and isinstance(post['data'], list):
        for item in post['data']:
            if 'post' in item: content.append(fix_encoding(item['post']))
            if 'text' in item: content.append(fix_encoding(item['text']))
    title = fix_encoding(post.get('title', ''))
    if not content and title: return title, ""
    return fix_encoding("\n\n".join(content)), title

def extract_date(post):
    keys = ['timestamp', 'creation_timestamp', 'date']
    ts = 0
    for k in keys:
        if k in post and post[k]: ts = post[k]; break
    if ts == 0: return "Unknown", None
    try:
        if ts > 10000000000: ts = ts / 1000
        dt = datetime.fromtimestamp(ts)
        return dt.strftime('%Y-%m-%d %H:%M'), dt
    except: return "Invalid", None

def scrape_facebook_url(url):
    try:
        if '?' in url: url = url.split('?')[0]
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
            html_content = response.read().decode('utf-8', errors='ignore')
            
        og_title = re.search(r'<meta property="og:title" content="([^"]+)"', html_content)
        og_desc = re.search(r'<meta property="og:description" content="([^"]+)"', html_content)
        og_image = re.search(r'<meta property="og:image" content="([^"]+)"', html_content)
        
        title = html.unescape(og_title.group(1)) if og_title else "Imported Post"
        desc = html.unescape(og_desc.group(1)) if og_desc else ""
        image_url = html.unescape(og_image.group(1)) if og_image else ""
        
        local_image_path = ""
        if image_url:
            import_dir = os.path.join(cfg.EXPORT_FOLDER_PATH, cfg.IMPORTED_MEDIA_DIR)
            if not os.path.exists(import_dir): os.makedirs(import_dir)
            filename = f"imported_{int(datetime.now().timestamp())}.jpg"
            local_full_path = os.path.join(import_dir, filename)
            try:
                with urllib.request.urlopen(image_url, context=ctx, timeout=10) as img_resp, open(local_full_path, 'wb') as out_file:
                    shutil.copyfileobj(img_resp, out_file)
                local_image_path = f"{cfg.IMPORTED_MEDIA_DIR}/{filename}"
            except: pass

        new_post = {
            "timestamp": int(datetime.now().timestamp()),
            "data": [{"post": desc}],
            "title": title,
            "attachments": []
        }
        if local_image_path:
            new_post["attachments"].append({"data": [{"media": {"uri": local_image_path, "title": "Imported"}}]})
        return True, new_post
    except Exception as e:
        return False, str(e)

def render_local_feed(page_num, f_search, f_start, f_end, f_len, f_media, f_sort, f_include_proc, hide_processed):
    # Filter
    filtered_list = []
    start_dt = datetime.strptime(f_start, '%Y-%m-%d') if f_start else None
    end_dt = datetime.strptime(f_end, '%Y-%m-%d') if f_end else None
    f_search = f_search.lower()
    f_len = int(f_len) if f_len else 0
    
    for i, post in enumerate(all_posts):
        is_proc = i in processed_indices
        if hide_processed and is_proc and not f_include_proc: continue
        
        text, _ = extract_content(post)
        if f_search and f_search not in text.lower(): continue
        if len(text) < f_len: continue
        # (Media check omitted for brevity, assumes text match mainly)
        
        date_str, dt_obj = extract_date(post)
        if start_dt and dt_obj and dt_obj < start_dt: continue
        if end_dt and dt_obj and dt_obj > end_dt: continue
        
        filtered_list.append((i, post))

    if f_sort == 'desc': filtered_list.reverse()
    
    # Paginate
    start_idx = (page_num - 1) * cfg.POSTS_PER_PAGE
    batch = filtered_list[start_idx:start_idx+cfg.POSTS_PER_PAGE]
    
    html_out = ""
    for idx, post in batch:
        date_str, _ = extract_date(post)
        text, title = extract_content(post)
        text_display = html.escape(text).replace('\n', '<br>')
        
        media_html = '<div class="media-grid">'
        for att in post.get('attachments', []):
             for d in att.get('data', []):
                 if 'media' in d:
                     uri = d['media'].get('uri', '')
                     if uri.endswith('.mp4'): media_html += f'<div class="media-item"><video controls src="{uri}"></video></div>'
                     else: media_html += f'<div class="media-item"><img src="{uri}" loading="lazy"></div>'
        media_html += '</div>'
        
        is_queued = idx in queued_indices
        is_processed = idx in processed_indices
        cls = "post"
        if is_queued: cls += " queued selected"
        if is_processed: cls += " processed"
        
        btn_txt = "Queued ✓" if is_queued else "Add"
        btn_cls = "btn btn-add active" if is_queued else "btn btn-add"
        
        # Escape JSON for embedding
        raw_json = html.escape(json.dumps(post))
        
        html_out += f"""
        <div class="{cls}" id="post-{idx}" onclick="togglePostSelect({idx}, event)">
            <div class="post-header">
                <div style="display:flex; align-items:center; gap:10px;" class="select-controls">
                    <input type="checkbox" name="post_select" value="{idx}" class="select-box" autocomplete="off" onclick="event.stopPropagation()">
                    <div class="range-marker" onclick="handleRangeClick(this, {idx}); event.stopPropagation()">&#8597;</div>
                    <div class="date">{date_str}</div>
                </div>
                <div style="display:flex; gap:10px; align-items:center;">
                    <button class="btn btn-secondary" style="padding:4px 8px; font-size:11px;" onclick="loadEditorForLocal({idx}); event.stopPropagation()">Edit</button>
                </div>
            </div>
            <div class="title">{title}</div>
            <div class="text">{text_display}</div>
            {media_html}
            <div class="actions">
                <button class="{btn_cls}" onclick="toggleQueue(this, {idx}); event.stopPropagation()">{btn_txt}</button>
            </div>
            <div id="debug-{idx}" class="raw-json">{raw_json}</div>
        </div>
        """
    return html_out