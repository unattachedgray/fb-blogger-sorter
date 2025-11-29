import http.server
import socketserver
import json
import os
import urllib.parse
import webbrowser
import threading
import time
import sys

# Import Modules
import curator_config as cfg
import curator_data as data_mod
import curator_wp as wp_mod
import curator_ai as ai_mod

# Initialize State
data_mod.load_processed_state()
data_mod.load_all_posts()

class CuratorHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        try:
            length = int(self.headers['Content-Length'])
            body = json.loads(self.rfile.read(length))
            
            # --- ROUTING ---
            if self.path == '/log_client_message':
                # Helper to log from JS to Python Console
                print(f"[Client] {body}")
                self.send_json({'status': 'ok'})
                return

            if self.path == '/api_upload_post':
                success, result = wp_mod.process_single_post_upload(
                    body['id'], body['wp_url'], body['wp_user'], body['wp_pass'], 
                    body.get('force_today', False), body.get('use_ai', False), body.get('gemini_key', ''),
                    body.get('custom_title'), body.get('custom_content'), body.get('custom_category'),
                    data_mod.all_posts
                )
                if success:
                    data_mod.mark_processed(body['id'])
                    data_mod.global_stats['posts'] += 1
                    data_mod.global_stats['images'] += result.get('imgs', 0)
                    data_mod.global_stats['videos'] += result.get('vids', 0)
                    data_mod.save_processed_state()
                    if body['id'] in data_mod.queued_indices: data_mod.queued_indices.remove(body['id'])
                    
                self.send_json({'success': success, 'wp_id': result.get('id'), 'wp_link': result.get('link'), 'error': result if not success else None})
                return

            if self.path == '/api_wp_update':
                # Learning Hook
                if 'content' in body and 'title' in body:
                    ai_mod.record_learning(body['content'], body['title'], body.get('category'))
                
                # Create Category if NEW
                cat_val = body.get('category')
                if cat_val and str(cat_val).startswith('NEW:'):
                    new_name = cat_val.split(':', 1)[1]
                    res = wp_mod.wp_api_call('categories', 'POST', {'name': new_name})
                    if 'id' in res: body['categories'] = [res['id']]
                threading.Thread(target=kill_me).start()
                self.send_json({'status': 'dying'})
                return

            if self.path == '/api_gemini_enhance':
                text = body.get('text', '')
                api_key = body.get('gemini_key', '')
                categories = body.get('categories', [])
                
                title, cat_id, _ = ai_mod.call_gemini_ai(text, [], api_key, categories)
                
                self.send_json({
                    'suggested_title': title,
                    'suggested_category_id': cat_id
                })
                return

            self.send_error(404)
            
        except Exception as e:
            print(f"Server Error (POST): {e}")
            self.send_error(500, str(e))

    def do_GET(self):
        try:
            parsed = urllib.parse.urlparse(self.path)
            query = urllib.parse.parse_qs(parsed.query)

            # --- STATIC FILES ---
            if self.path == '/' or self.path == '/index.html':
                with open('assets/index.html', 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Load Credentials
                creds = cfg.load_credentials()

                # Template Replacement
                content = content.replace('{STAT_REMAINING}', str(len(data_mod.all_posts) - len(data_mod.processed_indices)))
                content = content.replace('{STAT_PROCESSED}', str(len(data_mod.processed_indices)))
                content = content.replace('{STAT_QUEUED}', str(len(data_mod.queued_indices)))
                content = content.replace('{WP_URL}', creds.get('wp_url', ''))
                content = content.replace('{WP_USER}', creds.get('wp_user', ''))
                content = content.replace('{WP_PASS}', creds.get('wp_pass', ''))
                
                # Search/Filter State
                content = content.replace('{F_SEARCH}', '')
                content = content.replace('{F_START}', '')
                content = content.replace('{F_INCLUDE_PROC_CHECKED}', '')
                content = content.replace('{SEL_MEDIA_}', 'selected')
                content = content.replace('{SEL_MEDIA_IMAGES}', '')
                content = content.replace('{SEL_MEDIA_VIDEOS}', '')
                content = content.replace('{HIDE_CHECKED}', 'checked')
                content = content.replace('{STAT_REM_IMGS}', '0')
                content = content.replace('{STAT_REM_VIDS}', '0')
                content = content.replace('{STAT_Q_MEDIA}', '0')
                content = content.replace('{STAT_Q_SIZE}', '0')
                content = content.replace('{POSTS_HTML}', '') # Initial load empty, fetched via JS

                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(content.encode('utf-8'))
                return

            if self.path.startswith('/assets/') or self.path in ['/script.js', '/style.css']:
                try:
                    # Map root requests to assets folder
                    fname = self.path
                    if fname.startswith('/'): fname = fname[1:]
                    if not fname.startswith('assets/'): fname = 'assets/' + fname
                    
                    with open(fname, 'rb') as f:
                        self.send_response(200)
                        if self.path.endswith('.css'): self.send_header('Content-type', 'text/css')
                        elif self.path.endswith('.js'): self.send_header('Content-type', 'application/javascript')
                        self.end_headers()
                        self.wfile.write(f.read())
                    return
                except FileNotFoundError:
                    pass

            # --- API ENDPOINTS ---
            if parsed.path == '/get_status_data':
                creds = cfg.load_credentials()
                
                # Calculate Stats
                rem_imgs = 0
                rem_vids = 0
                q_media = 0
                
                # Iterate to find remaining media
                for idx, post in enumerate(data_mod.all_posts):
                    if idx in data_mod.processed_indices: continue
                    
                    p_imgs = 0
                    p_vids = 0
                    if 'attachments' in post:
                        for att in post['attachments']:
                            for d in att.get('data', []):
                                if 'media' in d:
                                    uri = d['media'].get('uri', '')
                                    if uri.endswith('.mp4') or uri.endswith('.mov'): p_vids += 1
                                    else: p_imgs += 1
                    
                    rem_imgs += p_imgs
                    rem_vids += p_vids
                    
                    if idx in data_mod.queued_indices:
                        q_media += (p_imgs + p_vids)

                skipped = max(0, len(data_mod.processed_indices) - data_mod.global_stats['posts'])
                data = {
                    "queue_count": len(data_mod.queued_indices),
                    "processed": len(data_mod.processed_indices),
                    "remaining": len(data_mod.all_posts) - len(data_mod.processed_indices),
                    "skipped": skipped,
                    "uploads": data_mod.global_stats,
                    "gemini_key": creds.get('gemini_key', ''),
                    "rem_images": rem_imgs,
                    "rem_videos": rem_vids,
                    "q_media": q_media,
                    "q_size": "0 MB",
                    "years_span": "All",
                    "ai_stats": ai_mod.ai_stats,
                    "logs": [] 
                }
                self.send_json(data)
                return

            if parsed.path == '/get_local_posts':
                page = int(query.get('page', [1])[0])
                search = query.get('search', [''])[0]
                start_date = query.get('start', [''])[0]
                inc_proc = query.get('inc_proc', ['0'])[0] == '1'
                media_filter = query.get('media', ['all'])[0]
                hide_proc = query.get('hide', ['0'])[0] == '1'
                uncat = query.get('uncat', ['0'])[0] == '1'
                
                # New params
                f_len = int(query.get('len', [0])[0])
                f_sort = query.get('sort', ['desc'])[0]
                f_end = None

                if uncat: hide_proc = True
                return

            if parsed.path == '/remove':
                idx = int(query['id'][0])
                if idx in data_mod.queued_indices: data_mod.queued_indices.remove(idx)
                self.send_json({'count': len(data_mod.queued_indices)})
                return

            if parsed.path == '/bulk_queue':
                ids = query['ids'][0].split(',')
                for i in ids: data_mod.queued_indices.add(int(i))
                self.send_json({'count': len(data_mod.queued_indices)})
                return
            
            if parsed.path == '/api_wp_list':
                per_page = query.get('per_page', ['10'])[0]
                page = query.get('page', ['1'])[0]
                category = query.get('category', [None])[0]
                
                params = {'per_page': per_page, 'page': page, 'status': 'publish'}
                
                # If category is 'uncategorized', we need to find the ID first.
                # For now, let's fetch categories first.
                cats, _ = wp_mod.wp_api_call('categories', 'GET', {'per_page': 100})
                
                if category == 'uncategorized':
                    # Find ID of 'Uncategorized'
                    uncat_id = next((c['id'] for c in cats if c['slug'] == 'uncategorized' or c['name'] == 'Uncategorized'), 1)
                    params['categories'] = uncat_id
                
                posts, headers = wp_mod.wp_api_call('posts', 'GET', params)
                
                # Get totals
                total_posts = headers.get('X-WP-Total', 0)
                
                # Get Uncategorized Count (separate call if not already filtered)
                total_uncat = 0
                if category == 'uncategorized':
                    total_uncat = total_posts
                else:
                    # Quick check for uncat count
                    uncat_id = next((c['id'] for c in cats if c['slug'] == 'uncategorized' or c['name'] == 'Uncategorized'), 1)
                    _, h_uncat = wp_mod.wp_api_call('posts', 'GET', {'categories': uncat_id, 'per_page': 1})
                    total_uncat = h_uncat.get('X-WP-Total', 0)

                self.send_json({
                    'posts': posts if isinstance(posts, list) else [],
                    'categories': cats if isinstance(cats, list) else [],
                    'total_posts': total_posts,
                    'total_uncategorized': total_uncat
                })
                return

            if parsed.path == '/api_diagnostics':
                import test_debug
                results = test_debug.run_diagnostics()
                self.send_json(results)
                return

            # Media Serving (Fallthrough)
            decoded_path = urllib.parse.unquote(self.path)
            if not decoded_path.startswith('/api_') and not decoded_path.startswith('/assets/'):
                full_path = os.path.join(cfg.EXPORT_FOLDER_PATH, decoded_path.lstrip('/'))
                if os.path.exists(full_path) and os.path.isfile(full_path):
                    self.send_response(200)
                    self.end_headers()
                    with open(full_path, 'rb') as f: self.wfile.write(f.read())
                    return
                
                # Check Imported Media
                full_path_imp = os.path.join(cfg.EXPORT_FOLDER_PATH, cfg.IMPORTED_MEDIA_DIR, os.path.basename(decoded_path))
                if os.path.exists(full_path_imp) and os.path.isfile(full_path_imp):
                    self.send_response(200)
                    self.end_headers()
                    with open(full_path_imp, 'rb') as f: self.wfile.write(f.read())
                    return

            self.send_error(404)
            
        except Exception as e:
            print(f"Server Error (GET): {e}")
            self.send_error(500, str(e))

    def send_json(self, data):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    print(f"--- FACEBOOK UPLOADER V52 RUNNING ---")
    print(f"1. Open http://localhost:{cfg.PORT}")
    with socketserver.ThreadingTCPServer(("", cfg.PORT), CuratorHandler) as httpd:
        webbrowser.open(f"http://localhost:{cfg.PORT}")
        httpd.serve_forever()