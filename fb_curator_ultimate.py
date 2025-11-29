import os
import json
import html
import http.server
import socketserver
import webbrowser
import urllib.parse
import urllib.request
import urllib.error
import base64
import ssl
from datetime import datetime
import math
import re
import threading
import sys
import mimetypes
import shutil
import random
import time

# --- CONFIGURATION ---
EXPORT_FOLDER_PATH = r'D:\temp\fb-blogger-sorter\facebook-misuchiru' 
POSTS_PER_PAGE = 50
PORT = 8000
PROCESSED_FILE = "processed_posts.json"
CREDENTIALS_FILE = "credentials.json"
IMPORTED_MEDIA_DIR = "imported_media"
LEARNING_FILE = "ai_learning.json"

# --- STATE ---
queued_indices = set()
processed_indices = set()
global_stats = {"posts": 0, "images": 0, "videos": 0}
all_posts = []
server_log_buffer = []
wp_cat_cache = []

# --- HTML TEMPLATE ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Facebook Curator & Uploader</title>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #f0f2f5; margin: 0; padding-top: 190px; padding-bottom: 150px; height: 100vh; box-sizing: border-box; overflow: hidden; }}
        
        /* HEADER */
        .header {{ background: #fff; padding: 10px 20px; position: fixed; top: 0; left: 0; right: 0; box-shadow: 0 4px 12px rgba(0,0,0,0.1); z-index: 1000; height: auto; min-height: 160px; box-sizing: border-box; display: flex; flex-direction: column; justify-content: center; gap: 8px; }}
        
        /* TABS */
        .tab-bar {{ display: flex; gap: 20px; border-bottom: 2px solid #f0f2f5; padding-bottom: 0; margin-bottom: 5px; }}
        .tab {{ padding: 10px 15px; cursor: pointer; font-weight: bold; color: #65676b; border-bottom: 3px solid transparent; }}
        .tab.active {{ color: #1877f2; border-bottom: 3px solid #1877f2; }}
        .tab:hover {{ background: #f0f2f5; border-radius: 6px 6px 0 0; }}
        
        /* TOP ROW */
        .header-row-top {{ display: flex; align-items: center; width: 100%; gap: 15px; }}
        h2 {{ margin: 0; font-size: 18px; white-space: nowrap; }}
        
        .conn-panel {{ display: flex; gap: 8px; align-items: center; font-size: 13px; background: #f7f8fa; padding: 6px 12px; border-radius: 6px; border: 1px solid #e5e5e5; }}
        .conn-input {{ padding: 5px; border: 1px solid #ccc; border-radius: 4px; font-size: 12px; width: 100px; }}
        .conn-summary {{ background: #f0fdf4; border: 1px solid #31a24c; padding: 6px 10px; border-radius: 6px; display: inline-flex; align-items: center; gap: 8px; font-size: 12px; color: #155724; white-space: nowrap; cursor: pointer; }}
        
        .ai-badge {{ background: linear-gradient(45deg, #6b4c9a, #a259ff); color: white; padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; display: flex; align-items: center; gap: 4px; }}
        
        .status-area {{ display: flex; align-items: center; gap: 10px; margin-left: auto; }}
        .status-panel {{ width: 280px; height: 45px; background: #222; color: #0f0; font-family: monospace; font-size: 11px; padding: 6px 10px; overflow-y: auto; border-radius: 6px; border: 1px solid #444; line-height: 1.4; white-space: nowrap; }}
        .status-panel a {{ color: #4db8ff; text-decoration: underline; }}
        
        .queue-count {{ font-size: 13px; font-weight: bold; color: #333; background: #eee; padding: 8px 12px; border-radius: 6px; min-width: 80px; text-align: center; }}
        
        .upload-btn {{ background: #1877f2; color: white; padding: 8px 16px; font-size: 13px; border: none; border-radius: 6px; font-weight: bold; cursor: pointer; white-space: nowrap; }}
        .upload-btn:disabled {{ background: #ccc; cursor: not-allowed; }}

        /* STATS BOX */
        .stats-box {{ display: flex; gap: 15px; font-size: 12px; color: #555; background: #fff; border: 1px solid #ddd; padding: 5px 10px; border-radius: 6px; margin-left: 10px; }}
        .stat-item {{ display: flex; flex-direction: column; align-items: center; line-height: 1.1; min-width: 40px; }}
        .stat-val {{ font-weight: bold; color: #1877f2; font-size: 14px; }}
        .stat-lbl {{ font-size: 9px; text-transform: uppercase; color: #777; margin-top: 2px; }}
        .stat-sep {{ border-left: 1px solid #eee; margin: 0 5px; }}

        /* BOTTOM ROW (Filters) */
        .header-row-bottom {{ display: flex; align-items: center; width: 100%; background: #f0f2f5; padding: 8px; border-radius: 8px; box-sizing: border-box; gap: 12px; border: 1px solid #e5e5e5; }}
        .filter-group {{ display: flex; align-items: center; gap: 5px; }}
        .filter-input {{ padding: 5px; border: 1px solid #ccc; border-radius: 4px; font-size: 12px; }}
        .filter-btn {{ background: #666; color: white; border: none; padding: 6px 12px; border-radius: 4px; font-weight: bold; cursor: pointer; font-size: 12px; }}
        .filter-btn:hover {{ background: #444; }}
        
        /* OPTION TOGGLES */
        .opts-group {{ margin-left: auto; display: flex; align-items: center; gap: 15px; font-size: 13px; color: #333; font-weight: 500; }}
        .opt-label {{ display: flex; align-items: center; gap: 6px; cursor: pointer; padding: 4px 8px; border-radius: 4px; background: white; border: 1px solid #ddd; }}
        .opt-label:hover {{ background: #f9f9f9; }}
        .opt-label input {{ accent-color: #1877f2; }}
        
        /* CONTENT AREAS */
        .tab-content {{ display: none; height: calc(100vh - 190px); overflow-y: auto; padding-bottom: 50px; }}
        .tab-content.active {{ display: block; }}
        
        /* LOCAL TAB STYLES */
        .local-container {{ max-width: 800px; margin: 0 auto; padding: 20px; }}
        .filter-bar-local {{ display: flex; align-items: center; gap: 10px; background: #f0f2f5; padding: 8px; border-radius: 8px; border: 1px solid #e5e5e5; }}
        
        /* POST STYLING */
        .post {{ background: #fff; padding: 20px; margin-bottom: 20px; border-radius: 8px; box-shadow: 0 1px 2px rgba(0,0,0,0.1); border-left: 5px solid transparent; position: relative; transition: all 0.2s; cursor: default; }}
        .post:hover {{ box-shadow: 0 2px 8px rgba(0,0,0,0.15); }}
        .post.selected {{ background: #e7f3ff; border-left: 5px solid #1877f2; }}
        .post.queued {{ border-left: 5px solid #31a24c; background: #f0fdf4; }}
        .post.processed {{ opacity: 0.6; filter: grayscale(0.8); }}
        .post.processed::after {{ content: "✓ Processed"; position: absolute; top: 10px; right: 10px; background: #eee; color: #555; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; }}
        .post.uploading {{ border-left: 5px solid #1877f2; background: #e7f3ff; opacity: 1; filter: none; }}
        .post.error {{ border-left: 5px solid #f00; background: #fff0f0; opacity: 1; filter: none; }}
        
        .post-header {{ display: flex; justify-content: space-between; margin-bottom: 10px; border-bottom: 1px solid #eee; padding-bottom: 10px; cursor: pointer; }}
        .date {{ color: #65676b; font-size: 13px; font-weight: bold; }}
        .debug-toggle {{ color: #aaa; font-size: 11px; text-decoration: underline; cursor: pointer; }}
        
        .title {{ font-style: italic; color: #444; margin-bottom: 8px; font-weight: bold; font-size: 15px; cursor: pointer; }}
        .title:hover {{ color: #1877f2; }}
        .text {{ font-size: 15px; line-height: 1.5; margin-bottom: 12px; color: #050505; white-space: pre-wrap; word-wrap: break-word; cursor: pointer; }}
        .text a {{ color: #1877f2; text-decoration: underline; position: relative; z-index: 10; }}
        
        /* MEDIA & LINKS */
        .media-grid {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }}
        .media-item {{ flex: 1 1 45%; max-width: 100%; border: 1px solid #eee; border-radius: 6px; overflow: hidden; background: #fafafa; }}
        .media-item img, .media-item video {{ width: 100%; height: auto; display: block; }}
        .media-caption {{ padding: 6px; font-size: 12px; color: #333; background: #f9f9f9; border-top: 1px solid #eee; font-style: italic; }}
        
        .link-card {{ border: 1px solid #e5e5e5; background: #f0f2f5; border-radius: 6px; margin-top: 10px; overflow: hidden; text-decoration: none; color: inherit; display: flex; transition: background 0.2s; min-height: 80px; position: relative; z-index: 10; }}
        .link-card:hover {{ background: #e4e6eb; }}
        .link-card-thumb {{ width: 80px; height: 80px; object-fit: cover; border-right: 1px solid #e5e5e5; flex-shrink: 0; background: #eee; display: flex; align-items: center; justify-content: center; font-size: 24px; color: #ccc; }}
        .link-card-content {{ padding: 8px 12px; flex-grow: 1; display: flex; flex-direction: column; justify-content: center; overflow: hidden; }}
        .link-title {{ font-weight: bold; font-size: 14px; margin-bottom: 2px; }}
        .link-desc {{ font-size: 11px; color: #606770; margin-top: 2px; }}
        .link-url {{ font-size: 10px; color: #65676b; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-top: 2px; }}
        
        /* ACTIONS */
        .actions {{ margin-top: 15px; display: flex; gap: 10px; align-items: center; position: relative; z-index: 10; }}
        .btn {{ padding: 8px 16px; border-radius: 6px; font-weight: bold; cursor: pointer; border: none; font-size: 13px; transition: 0.2s; }}
        .btn-add {{ background: #e7f3ff; color: #1877f2; }}
        .btn-add:hover {{ background: #dbe7f2; }}
        .btn-add.active {{ background: #31a24c; color: white; }}
        .btn-proc {{ background: #f0f2f5; color: #65676b; }}
        .btn-proc:hover {{ background: #e4e6eb; }}
        
        /* CHECKBOX & RANGE */
        .select-controls {{ display:flex; align-items:center; gap:8px; position: relative; z-index: 10; }}
        .select-box {{ width: 24px; height: 24px; cursor: pointer; accent-color: #1877f2; }}
        .range-marker {{ width: 28px; height: 28px; display:flex; align-items:center; justify-content:center; border:1px solid #ccc; border-radius:4px; cursor:pointer; color:#ccc; font-weight:bold; font-size:14px; user-select: none; background: #fff; }}
        .range-marker:hover {{ border-color:#1877f2; color:#1877f2; }}
        .range-marker.active {{ background:#1877f2; color:white; border-color:#1877f2; }}
        
        /* FLOATING ACTION BUTTONS */
        .floating-upload {{ position: fixed; right: 30px; top: 240px; z-index: 2000; }}
        .floating-bottom {{ position: fixed; right: 30px; bottom: 30px; display: flex; flex-direction: column; gap: 12px; z-index: 2000; }}
        
        .fab-btn {{ width: 180px; padding: 14px; border: none; border-radius: 30px; font-weight: bold; font-size: 15px; cursor: pointer; box-shadow: 0 4px 12px rgba(0,0,0,0.3); text-align: center; transition: transform 0.2s; display: flex; align-items: center; justify-content: center; gap: 10px; }}
        .fab-btn:hover {{ transform: scale(1.05); }}
        .fab-btn:active {{ transform: scale(0.95); }}
        .fab-upload {{ background: #1877f2; color: white; }}
        .fab-skip {{ background: #65676b; color: white; }}
        .fab-select {{ background: #fff; color: #333; border: 2px solid #ddd; }}
        .fab-select:hover {{ background: #f0f2f5; border-color: #ccc; }}
        
        /* WP ENHANCE STYLES */
        .enhance-layout {{ display: flex; height: 100%; }}
        .enhance-sidebar {{ width: 300px; border-right: 1px solid #ddd; background: #fff; display: flex; flex-direction: column; }}
        .enhance-list {{ flex-grow: 1; overflow-y: auto; }}
        .enhance-item {{ padding: 15px; border-bottom: 1px solid #eee; cursor: pointer; transition: 0.2s; }}
        .enhance-item:hover {{ background: #f7f8fa; }}
        .enhance-item.active {{ background: #e7f3ff; border-left: 4px solid #1877f2; }}
        .enhance-title {{ font-weight: bold; font-size: 13px; margin-bottom: 4px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }}
        .enhance-meta {{ font-size: 11px; color: #666; display: flex; justify-content: space-between; }}
        .enhance-main {{ flex-grow: 1; padding: 20px; overflow-y: auto; background: #f9f9f9; display: flex; flex-direction: column; gap: 20px; }}
        .enhance-card {{ background: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .editor-row {{ margin-bottom: 15px; }}
        .editor-label {{ display: block; font-size: 12px; font-weight: bold; color: #555; margin-bottom: 5px; text-transform: uppercase; }}
        .editor-input {{ width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; box-sizing: border-box; }}
        .editor-select {{ width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; }}
        .content-preview {{ border: 1px solid #ddd; padding: 20px; border-radius: 6px; min-height: 200px; background: #fff; line-height: 1.6; }}
        .content-preview img, .content-preview video {{ max-width: 100%; height: auto; display: block; margin: 10px 0; border-radius: 4px; }}
        .enhance-actions {{ display: flex; gap: 10px; justify-content: flex-end; padding: 20px; background: #fff; border-top: 1px solid #ddd; position: sticky; bottom: 0; }}
        .btn-primary {{ background: #1877f2; color: white; }}
        .btn-secondary {{ background: #e4e6eb; color: #333; }}
        .btn-magic {{ background: linear-gradient(45deg, #6b4c9a, #a259ff); color: white; }}
        
        /* ROLLING UI */
        #rolling-container {{ display: none; flex-grow: 1; overflow-y: auto; padding: 20px; background: #f0f2f5; }}
        .rolling-controls {{ background: #fff; padding: 15px; border-bottom: 1px solid #ddd; display: flex; justify-content: space-between; align-items: center; }}
        .rolling-card {{ background: #fff; border: 1px solid #ddd; border-radius: 8px; padding: 15px; display: flex; gap: 15px; align-items: flex-start; margin-bottom: 15px; transition: all 0.3s; opacity: 0; transform: translateY(20px); animation: slideIn 0.3s forwards; }}
        @keyframes slideIn {{ to {{ opacity: 1; transform: translateY(0); }} }}
        .rolling-card.updating {{ border-color: #1877f2; background: #f0f8ff; }}
        .rolling-check {{ margin-top: 5px; transform: scale(1.3); cursor: pointer; }}
        .rolling-content {{ flex-grow: 1; }}
        .rolling-status {{ font-size: 11px; font-weight: bold; color: #666; text-transform: uppercase; margin-bottom: 5px; }}
        
        .load-more-btn {{ background: #fff; border: 2px solid #1877f2; color: #1877f2; padding: 12px 30px; border-radius: 30px; font-size: 14px; font-weight: bold; cursor: pointer; margin: 20px auto; display: block; }}
        .live-box {{ background: #fff; padding: 30px; border-radius: 8px; text-align: center; margin-top: 30px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }}
        .live-input {{ width: 60%; padding: 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 16px; margin-bottom: 15px; }}
        .live-btn {{ background: #1877f2; color: white; padding: 12px 30px; border: none; border-radius: 6px; font-size: 16px; cursor: pointer; }}
        .raw-json {{ display: none; background: #333; color: #0f0; padding: 10px; margin-top: 10px; overflow-x: auto; border-radius: 4px; font-family: monospace; font-size: 0.8em; position: relative; z-index: 15; }}
    </style>
    <script>
        function switchTab(tabId) {{
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.getElementById(tabId).classList.add('active');
            document.getElementById('btn-' + tabId).classList.add('active');
        }}
        
        function log(msg) {{
            const panel = document.getElementById('status-log');
            if(panel) {{
                panel.innerHTML += `<div>[`+(new Date().toLocaleTimeString())+`] `+msg+`</div>`;
                panel.scrollTop = panel.scrollHeight;
            }}
            fetch('/log_client_message', {{ method: 'POST', body: msg }});
        }}

        // --- LOCAL CURATOR LOGIC ---
        let CURRENT_PAGE = 1;
        let IS_LOADING = false;

        function loadMorePosts() {{
            if (IS_LOADING) return;
            IS_LOADING = true;
            const btn = document.getElementById('load-more-btn');
            if(btn) btn.innerText = "Loading...";
            
            const params = new URLSearchParams(window.location.search);
            params.set('page', CURRENT_PAGE + 1);
            params.set('ajax', '1');
            
            fetch('/?' + params.toString()).then(res => res.json()).then(data => {{
                document.getElementById('posts-wrapper').insertAdjacentHTML('beforeend', data.html);
                CURRENT_PAGE++;
                IS_LOADING = false;
                if(btn) btn.innerText = "Load More Posts";
                if(data.html.trim() === "") if(btn) btn.style.display = 'none';
            }}).catch(err => {{ IS_LOADING = false; }});
        }}
        
        function resetAndReload() {{
             document.getElementById('posts-wrapper').innerHTML = ""; 
             CURRENT_PAGE = 0;
             const btn = document.getElementById('load-more-btn');
             if(btn) btn.style.display = 'block';
             loadMorePosts();
        }}
        
        function togglePostSelect(id, event) {{
            if (window.getSelection().toString().length > 0) return;
            if (event && event.target.tagName === 'A') return;
            const cb = document.querySelector(`input[value="${{id}}"]`);
            if(cb) {{ cb.checked = !cb.checked; updatePostStyle(id, cb.checked); }}
        }}
        
        function updatePostStyle(id, isChecked) {{
            const row = document.getElementById('post-' + id);
            if(row) {{
                if(isChecked) row.classList.add('selected');
                else row.classList.remove('selected');
            }}
        }}
        
        function toggleSelectAll() {{
            const checkboxes = Array.from(document.getElementsByName('post_select'));
            const allChecked = checkboxes.every(cb => cb.checked);
            checkboxes.forEach(cb => {{ cb.checked = !allChecked; updatePostStyle(cb.value, !allChecked); }});
        }}

        // --- RANGE SELECTION ---
        let rangeStartId = null;
        function handleRangeClick(el, id) {{
            if (rangeStartId === null) {{
                rangeStartId = id; el.classList.add('active'); el.innerHTML = '&darr;';
            }} else {{
                selectRange(rangeStartId, id);
                setTimeout(() => {{
                    document.querySelectorAll('.range-marker').forEach(m => {{ m.classList.remove('active'); m.innerHTML = '&#8597;'; }});
                }}, 500);
                rangeStartId = null;
            }}
        }}
        function selectRange(startId, endId) {{
            const checkboxes = Array.from(document.getElementsByName('post_select'));
            let startIndex = -1, endIndex = -1;
            checkboxes.forEach((cb, idx) => {{
                if (cb.value == startId) startIndex = idx;
                if (cb.value == endId) endIndex = idx;
            }});
            if (startIndex > endIndex) {{ const t = startIndex; startIndex = endIndex; endIndex = t; }}
            for(let i = startIndex; i <= endIndex; i++) {{ 
                checkboxes[i].checked = true; 
                updatePostStyle(checkboxes[i].value, true);
            }}
        }}
        
        // --- UPLOAD & BULK ---
        function executeBulk(action) {{
            const checkboxes = Array.from(document.getElementsByName('post_select'));
            const checked = checkboxes.filter(cb => cb.checked);
            const ids = checked.map(cb => cb.value);
            
            if (ids.length === 0) return alert("No posts selected!");
            
            const autoProcess = document.getElementById('auto-process-rest').checked;
            const uncheckedIds = checkboxes.filter(cb => !cb.checked).map(cb => cb.value);
            const hideCheckbox = document.getElementById('hide-processed-chk');

            if (action === 'queue') {{
                fetch('/bulk_queue?ids=' + ids.join(',')).then(() => {{
                    fetch('/bulk_process?ids=' + ids.join(',')).then(() => {{
                        ids.forEach(id => {{
                            const row = document.getElementById('post-' + id);
                            if(row) {{
                                if(hideCheckbox && hideCheckbox.checked) {{ row.remove(); }}
                                else {{
                                    row.classList.add('queued', 'processed');
                                    row.classList.remove('selected');
                                    row.style.opacity = "0.5";
                                    row.querySelector('.btn-add').classList.add('active');
                                    row.querySelector('.btn-add').innerText = "Queued";
                                }}
                            }}
                        }});
                        checkboxes.forEach(cb => {{ cb.checked = false; }});
                        runUploadWorker();
                        
                        if (autoProcess && uncheckedIds.length > 0) {{
                            fetch('/bulk_process?ids=' + uncheckedIds.join(',')).then(() => {{
                                uncheckedIds.forEach(id => {{
                                    const row = document.getElementById('post-' + id);
                                    if(row) row.remove();
                                }});
                                if(document.querySelectorAll('.post').length < 5) resetAndReload();
                            }});
                        }}
                    }});
                }});
            }} else if (action === 'process') {{
                fetch('/bulk_process?ids=' + ids.join(',')).then(() => {{
                    ids.forEach(id => {{
                        const row = document.getElementById('post-' + id);
                        if(row) {{
                            if(hideCheckbox && hideCheckbox.checked) {{ row.remove(); }}
                            else {{
                                row.classList.add('processed');
                                row.classList.remove('selected');
                                row.style.opacity = "0.5";
                            }}
                        }}
                    }});
                    checkboxes.forEach(cb => {{ cb.checked = false; }});
                    
                    if (autoProcess && uncheckedIds.length > 0) {{
                        fetch('/bulk_queue?ids=' + uncheckedIds.join(',')).then(() => {{
                             fetch('/bulk_process?ids=' + uncheckedIds.join(',')).then(() => {{
                                uncheckedIds.forEach(id => {{
                                    const row = document.getElementById('post-' + id);
                                    if(row) {{
                                        if(hideCheckbox && hideCheckbox.checked) row.remove();
                                        else {{ 
                                            row.classList.add('queued', 'processed'); 
                                            row.style.opacity = "0.5";
                                        }}
                                    }}
                                }});
                                runUploadWorker();
                                if(document.querySelectorAll('.post').length < 5) resetAndReload();
                             }});
                        }});
                    }}
                }});
            }}
        }}
        
        let isUploading = false;
        async function runUploadWorker() {{
            if (isUploading) return;
            
            const url = document.getElementById('wp_url').value.replace(/\/$/, "");
            const user = document.getElementById('wp_user').value;
            const pass = document.getElementById('wp_pass').value;
            const forceToday = document.getElementById('force-today').checked;
            const useAI = document.getElementById('use-ai').checked;
            const geminiKey = document.getElementById('gemini_key').value;
            
            if (!url || !user || !pass) return; 
            
            const res = await fetch('/get_queue_ids');
            const data = await res.json();
            const ids = data.ids;
            
            if (ids.length === 0) return;
            
            isUploading = true;
            const qDisplay = document.getElementById('queue-count');
            if(qDisplay) qDisplay.innerText = ids.length + " Uploading...";
            
            const id = ids[0];
            log(useAI ? "✨ AI Processing #" + id + "..." : "Uploading #" + id + "...");
            
            try {{
                const uploadRes = await fetch('/api_upload_post', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{ 
                        id: id, 
                        wp_url: url, wp_user: user, wp_pass: pass, 
                        force_today: forceToday,
                        use_ai: useAI,
                        gemini_key: geminiKey
                    }})
                }});
                const result = await uploadRes.json();
                if (result.success) {{
                    log(`✓ OK: <a href="${{result.wp_link}}" target="_blank">View Post</a>`);
                    await fetch('/remove?id=' + id);
                }} else {{
                    log("❌ Error: " + result.error);
                    await fetch('/remove?id=' + id);
                }}
            }} catch (e) {{ log("Net Err: " + e); }}
            
            isUploading = false;
            setTimeout(runUploadWorker, 1000); 
        }}
        
        // --- POLLER ---
        setInterval(() => {{
            fetch('/get_status_data').then(r => r.json()).then(data => {{
                const qCount = document.getElementById('queue-count');
                if(qCount) qCount.innerText = data.queue_count + (isUploading ? " Uploading..." : " Queued");
                
                if(!document.getElementById('gemini_key').value && data.gemini_key) 
                    document.getElementById('gemini_key').value = data.gemini_key;
                    
                if(document.getElementById('stat-proc')) document.getElementById('stat-proc').innerText = data.processed;
                if(document.getElementById('stat-rem')) document.getElementById('stat-rem').innerText = data.remaining;
                if(document.getElementById('stat-rem-img')) document.getElementById('stat-rem-img').innerText = data.rem_images;
                if(document.getElementById('stat-rem-vid')) document.getElementById('stat-rem-vid').innerText = data.rem_videos;
                if(document.getElementById('stat-up')) document.getElementById('stat-up').innerText = data.uploads.posts;
                if(document.getElementById('stat-img')) document.getElementById('stat-img').innerText = data.uploads.images;
                if(document.getElementById('stat-vid')) document.getElementById('stat-vid').innerText = data.uploads.videos;
                if(document.getElementById('stat-skip')) document.getElementById('stat-skip').innerText = data.skipped;
                if(document.getElementById('stat-pct')) {{
                    let pct = Math.round((data.processed / (data.processed + data.remaining)) * 100) || 0;
                    document.getElementById('stat-pct').innerText = pct + "%";
                }}
                if(document.getElementById('stat-years')) document.getElementById('stat-years').innerText = data.years_span;
                if(document.getElementById('stat-q-media')) document.getElementById('stat-q-media').innerText = data.q_media;
                if(document.getElementById('stat-q-size')) document.getElementById('stat-q-size').innerText = data.q_size;
                
                const logPanel = document.getElementById('status-log');
                if (logPanel && logPanel.children.length < 2 && data.logs.length > 0) {{
                    logPanel.innerHTML = "";
                    data.logs.forEach(l => {{
                         const line = document.createElement('div');
                         line.innerHTML = l;
                         logPanel.appendChild(line);
                    }});
                    logPanel.scrollTop = logPanel.scrollHeight;
                }}
            }});
        }}, 2000);
        
        function applyFilters() {{
            const params = new URLSearchParams();
            ['f_start', 'f_end', 'f_len', 'f_media', 'f_sort', 'f_search'].forEach(id => {{
                const val = document.getElementById(id).value;
                if(val) params.set(id.replace('f_', ''), val);
            }});
            const hideCb = document.getElementById('hide-processed-chk');
            params.set('hide', hideCb.checked ? '1' : '0');
            const incProc = document.getElementById('f_include_proc');
            params.set('inc_proc', incProc.checked ? '1' : '0');
            window.location.search = params.toString();
        }}
        
        function handleSearchKey(e) {{ if (e.key === 'Enter') applyFilters(); }}
        
        function toggleHideProcessed(cb) {{
            const params = new URLSearchParams(window.location.search);
            params.set('hide', cb.checked ? '1' : '0');
            params.set('page', '1'); 
            window.location.search = params.toString();
        }}
        
        function toggleDebug(id) {{
            var el = document.getElementById('debug-' + id);
            el.style.display = el.style.display === 'none' ? 'block' : 'none';
        }}
        
        function toggleQueue(btn, idx) {{
             const isQueued = btn.classList.contains('active');
             const endpoint = isQueued ? '/remove' : '/add';
             if(!isQueued) {{
                 btn.classList.add('active'); btn.innerText="Queued";
                 btn.closest('.post').classList.add('queued');
                 const post = btn.closest('.post');
                 const hide = document.getElementById('hide-processed-chk');
                 fetch(endpoint + '?id=' + idx).then(()=>{{
                     fetch('/mark_processed?id=' + idx);
                     if(hide && hide.checked) {{ post.remove(); }}
                     else {{ post.classList.add('processed'); post.style.opacity="0.5"; }}
                     runUploadWorker();
                 }});
             }} else {{
                 btn.classList.remove('active'); btn.innerText="Add";
                 btn.closest('.post').classList.remove('queued');
                 fetch(endpoint + '?id=' + idx);
             }}
        }}
        
        function markProcessed(btn, idx) {{
            fetch('/mark_processed?id=' + idx).then(()=>{{
                const post = btn.closest('.post');
                const hide = document.getElementById('hide-processed-chk');
                if(hide && hide.checked) post.remove();
                else {{ post.classList.add('processed'); post.style.opacity="0.5"; btn.innerText="Done"; btn.disabled=true; }}
            }});
        }}

        // --- WP ENHANCE LOGIC ---
        let wpPosts = [];
        let currentWpPost = null;
        let wpCategories = [];
        
        // ROLLING LOGIC
        let rollingQueue = [];
        let rollingActive = false;
        let rollingPage = 1;
        let isFetchingBatch = false;
        let isUpdatingItem = false;

        function toggleRollingMode() {{
            const singleView = document.getElementById('enhance-single-view');
            const rollingView = document.getElementById('rolling-container');
            
            if(rollingView.style.display === 'none') {{
                // Start Rolling
                singleView.style.display = 'none';
                rollingView.style.display = 'block';
                document.getElementById('btn-rolling-toggle').innerText = "Switch to Single";
                document.querySelector('.enhance-sidebar').style.display = 'none';
                rollingActive = true;
                rollingPage = 1;
                rollingQueue = [];
                document.getElementById('rolling-list').innerHTML = "";
                fetchRollingBatch();
                processRollingQueue(); // Start the loop
            }} else {{
                // Stop Rolling
                rollingActive = false;
                singleView.style.display = 'flex';
                rollingView.style.display = 'none';
                document.querySelector('.enhance-sidebar').style.display = 'flex';
                document.getElementById('btn-rolling-toggle').innerText = "Start Rolling Auto-Pilot";
            }}
        }}
        
        function fetchRollingBatch() {{
            if(isFetchingBatch || !rollingActive) return;
            isFetchingBatch = true;
            log("Fetching next batch for Rolling...");
            
            const params = new URLSearchParams();
            params.set('category', 'uncategorized');
            params.set('per_page', '5'); // Fetch chunks
            params.set('page', rollingPage);
            
            fetch('/api_wp_list?' + params.toString()).then(r => r.json()).then(data => {{
                if(!data.posts || data.posts.length === 0) {{
                    log("No more posts to fetch.");
                    isFetchingBatch = false;
                    return;
                }}
                
                wpCategories = data.categories; // Ensure cats are loaded
                
                // Prepare Batch for AI
                const batchPayload = data.posts.map(p => ({{
                    id: p.id,
                    title: p.title.rendered,
                    content: p.content.rendered.replace(/<[^>]+>/g, '').trim().substring(0, 3000)
                }}));
                
                fetch('/api_gemini_enhance_batch', {{
                    method: 'POST',
                    body: JSON.stringify({{ posts: batchPayload, categories: wpCategories }})
                }}).then(r => r.json()).then(aiResults => {{
                    // Merge and Add to Queue
                    aiResults.forEach((res, idx) => {{
                         const original = data.posts[idx];
                         const item = {{
                             original: original,
                             ai: res,
                             status: 'ready', // pending update
                             domId: 'rolling-' + original.id
                         }};
                         rollingQueue.push(item);
                         renderRollingItem(item);
                    }});
                    
                    rollingPage++;
                    isFetchingBatch = false;
                }}).catch(e => {{
                    console.error(e);
                    isFetchingBatch = false;
                }});
            }});
        }}
        
        function renderRollingItem(item) {{
            const container = document.getElementById('rolling-list');
            let catOptions = `<option value="">-- Select --</option>`;
            wpCategories.forEach(c => {{
                const selected = (item.ai.suggested_category_id == c.id) ? "selected" : "";
                catOptions += `<option value="${{c.id}}" ${{selected}}>${{c.name}}</option>`;
            }});
            
            const html = `
            <div class="rolling-card" id="${{item.domId}}">
                <input type="checkbox" class="rolling-check" checked id="check-${{item.original.id}}">
                <div class="rolling-content">
                    <div class="rolling-status" id="status-${{item.original.id}}">WAITING IN BUFFER...</div>
                    <div class="editor-row" style="margin-bottom:5px;">
                        <input type="text" class="editor-input" id="title-${{item.original.id}}" value="${{item.ai.suggested_title}}">
                    </div>
                    <div class="editor-row" style="margin-bottom:5px; display:flex; gap:10px;">
                        <select class="editor-select" id="cat-${{item.original.id}}" style="width:50%;">${{catOptions}}</select>
                        <div style="font-size:11px; color:#888; align-self:center;">ID: #${{item.original.id}}</div>
                    </div>
                    <div style="font-size:12px; color:#555;">${{item.original.content.rendered.replace(/<[^>]+>/g, '').substring(0, 150)}}...</div>
                </div>
            </div>
            `;
            container.insertAdjacentHTML('beforeend', html);
        }}
        
        function processRollingQueue() {{
            if(!rollingActive) return;
            
            // Check Buffer: We want at least 5 items in queue before we start updating the top one
            // This gives user time to react.
            // Also ensure we are not currently updating one.
            
            if(!isUpdatingItem && rollingQueue.length >= 5) {{
                const item = rollingQueue[0]; // Get top item
                const checkbox = document.getElementById('check-' + item.original.id);
                
                if(checkbox && checkbox.checked && !document.getElementById('pause-rolling').checked) {{
                    updateRollingItem(item);
                }} else if (checkbox && !checkbox.checked) {{
                    // If unchecked, user skipped it. Remove and move on.
                    rollingQueue.shift();
                    document.getElementById(item.domId).remove();
                }}
            }}
            
            // Refill if low
            if(rollingQueue.length < 5 && !isFetchingBatch) {{
                fetchBatchWpPosts();
            }}
            
            setTimeout(processRollingQueue, 2000); // Check loop every 2s
        }}
        
        function updateRollingItem(item) {{
            isUpdatingItem = true;
            const dom = document.getElementById(item.domId);
            dom.classList.add('updating');
            document.getElementById('status-' + item.original.id).innerText = "UPDATING...";
            
            // Get latest values from inputs (in case user edited)
            const title = document.getElementById('title-' + item.original.id).value;
            const cat = document.getElementById('cat-' + item.original.id).value;
            
            fetch('/api_wp_update', {{
                method: 'POST',
                body: JSON.stringify({{
                    id: item.original.id,
                    title: title,
                    category: cat,
                    content: item.original.content.rendered // keep original content body
                }})
            }}).then(r => r.json()).then(data => {{
                isUpdatingItem = false;
                if(data.success) {{
                    // Success! Remove from UI and Queue
                    dom.style.transition = "all 0.5s";
                    dom.style.opacity = "0";
                    dom.style.transform = "translateX(50px)";
                    setTimeout(() => dom.remove(), 500);
                    rollingQueue.shift(); // Remove from head
                }} else {{
                    // Error, leave it but mark error
                    document.getElementById('status-' + item.original.id).innerText = "ERROR: " + data.error;
                    dom.style.borderColor = "red";
                    // We remove it from queue to prevent block? Or pause?
                    // Let's pause to let user see error
                    document.getElementById('pause-rolling').checked = true;
                }}
            }}).catch(e => {{
                isUpdatingItem = false;
                document.getElementById('status-' + item.original.id).innerText = "NET ERROR";
            }});
        }}
        
        function loadEditorForLocal(idx) {{
            isLocalMode = true;
            currentEditorId = idx;
            switchTab('enhance');
            const rawJson = document.getElementById('debug-' + idx).innerText;
            const post = JSON.parse(rawJson);
            const title = post.title || "New Post";
            let content = "";
            if (post.data && post.data.length > 0) content = post.data[0].post || "";
            document.getElementById('edit-title').value = title;
            document.getElementById('edit-content').innerText = content;
            document.querySelector('.enhance-sidebar').style.display = 'none';
            document.querySelector('.enhance-main').style.marginLeft = '0';
            document.getElementById('btn-update').innerText = "Upload to WP";
            fetch('/api_wp_list').then(r=>r.json()).then(data => {{
                wpCategories = data.categories;
                populateCategorySelect();
            }});
        }}
        
        function fetchWpPosts(reset=false) {{
            isLocalMode = false;
            document.querySelector('.enhance-sidebar').style.display = 'flex';
            const btn = document.getElementById('wp-fetch-btn');
            btn.innerText = "Fetching...";
            btn.disabled = true;
            const params = new URLSearchParams();
            if(document.getElementById('wp-filter-uncat').checked) params.set('category', 'uncategorized');
            const search = document.getElementById('wp-search').value;
            if(search) params.set('search', search);
            fetch('/api_wp_list?' + params.toString()).then(r => r.json()).then(data => {{
                if(data.error) {{ alert(data.error); return; }}
                wpPosts = data.posts;
                wpCategories = data.categories;
                const listEl = document.getElementById('wp-post-list'); listEl.innerHTML = "";
                wpPosts.forEach((p, idx) => {{
                    const date = new Date(p.date).toLocaleDateString();
                    const div = document.createElement('div'); div.className = 'enhance-item'; div.id = 'wp-item-' + idx;
                    div.onclick = () => loadWpPost(idx);
                    div.innerHTML = `<div class="enhance-title">${{p.title.rendered}}</div>`;
                    listEl.appendChild(div);
                }});
                if(wpPosts.length > 0) loadWpPost(0);
                btn.innerText = "Fetch Posts"; btn.disabled = false;
                populateCategorySelect();
            }});
        }}
        function loadWpPost(idx) {{
            isLocalMode = false;
            currentEditorId = wpPosts[idx].id;
            currentWpPost = wpPosts[idx];
            document.querySelectorAll('.enhance-item').forEach(i => i.classList.remove('active'));
            document.getElementById('wp-item-' + idx).classList.add('active');
            document.getElementById('edit-title').value = currentWpPost.title.rendered;
            document.getElementById('edit-content').innerHTML = currentWpPost.content.rendered;
            const catSelect = document.getElementById('edit-category');
            if(currentWpPost.categories && currentWpPost.categories.length > 0) catSelect.value = currentWpPost.categories[0];
            document.getElementById('btn-update').innerText = "Update & Next";
        }}
        function populateCategorySelect() {{
            const sel = document.getElementById('edit-category');
            sel.innerHTML = '<option value="">-- Select Category --</option>';
            wpCategories.forEach(c => {{
                const opt = document.createElement('option');
                opt.value = c.id; opt.innerText = c.name; sel.appendChild(opt);
            }});
            const newOpt = document.createElement('option');
            newOpt.value = "new"; newOpt.innerText = "+ Create New Category..."; sel.appendChild(newOpt);
        }}
        function checkNewCategory(sel) {{
            if(sel.value === 'new') {{
                const name = prompt("Enter new category name:");
                if(name) {{
                    const opt = document.createElement('option');
                    opt.innerText = name + " (New)"; opt.value = "NEW:" + name; opt.selected = true; sel.add(opt, 1);
                }} else {{ sel.value = ""; }}
            }}
        }}
        function runAiEnhance() {{
             const btn = document.getElementById('btn-ai'); btn.innerText="Thinking...";
             const content = document.getElementById('edit-content').innerText;
             const title = document.getElementById('edit-title').value;
             fetch('/api_gemini_enhance', {{
                 method: 'POST',
                 body: JSON.stringify({{ text: content, title: title, categories: wpCategories }})
             }}).then(r=>r.json()).then(d=>{{
                 if(d.suggested_title && !d.suggested_title.startsWith("Error")) {{
                    document.getElementById('edit-title').value = d.suggested_title;
                    if(d.suggested_category_id) document.getElementById('edit-category').value = d.suggested_category_id;
                    if(typeof d.suggested_category_id === 'string' && d.suggested_category_id.startsWith('NEW:')) {{
                        const sel = document.getElementById('edit-category');
                        const opt = document.createElement('option');
                        opt.innerText = d.suggested_category_id.split(':')[1] + " (AI)";
                        opt.value = d.suggested_category_id;
                        opt.selected = true;
                        sel.add(opt, 1);
                    }}
                 }} else {{
                    alert("AI Error: " + d.suggested_title); 
                 }}
                 btn.innerText="Magic Enhance";
             }});
        }}
        function distributeMedia() {{
             const container = document.createElement('div');
             container.innerHTML = document.getElementById('edit-content').innerHTML;
             const figs = Array.from(container.querySelectorAll('figure'));
             const ps = Array.from(container.querySelectorAll('p'));
             figs.forEach(f=>f.remove());
             const topCount = Math.min(5, figs.length);
             for(let i=topCount-1; i>=0; i--) container.prepend(figs[i]);
             let fIdx = topCount;
             for(let i=0; i<ps.length; i++) {{
                 if(i>0 && i%2==0 && fIdx<figs.length) {{ ps[i].after(figs[fIdx]); fIdx++; }}
             }}
             while(fIdx < figs.length) {{ container.append(figs[fIdx]); fIdx++; }}
             document.getElementById('edit-content').innerHTML = container.innerHTML;
        }}
        function updateWpPost(autoNext) {{
            const btn = document.getElementById('btn-update'); btn.innerText="Saving..."; btn.disabled=true;
            const title = document.getElementById('edit-title').value;
            const content = document.getElementById('edit-content').innerHTML;
            const catVal = document.getElementById('edit-category').value;
            
            const url = document.getElementById('wp_url').value.replace(/\/$/, "");
            const user = document.getElementById('wp_user').value;
            const pass = document.getElementById('wp_pass').value;
            const forceToday = document.getElementById('force-today').checked;
            
            if (isLocalMode) {{
                 fetch('/api_upload_post', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{ 
                        id: currentEditorId, 
                        wp_url: url, wp_user: user, wp_pass: pass, force_today: forceToday,
                        custom_title: title, custom_content: content, custom_category: catVal
                    }})
                }}).then(r => r.json()).then(data => {{
                     btn.disabled = false; btn.innerText = "Upload to WP";
                     if(data.success) {{
                         alert("Uploaded!"); switchTab('local');
                         document.getElementById('post-' + currentEditorId).remove();
                         fetch('/mark_processed?id=' + currentEditorId);
                     }} else {{ alert("Error: " + data.error); }}
                }});
            }} else {{
                fetch('/api_wp_update', {{
                    method: 'POST',
                    body: JSON.stringify({{ id: currentWpPost.id, title: title, content: content, category: catVal }})
                }}).then(r=>r.json()).then(d=>{{
                    btn.disabled=false; btn.innerText="Update & Next";
                    if(d.success) {{
                        log("Updated Post #" + currentWpPost.id);
                        const idx = wpPosts.indexOf(currentWpPost);
                        document.getElementById('wp-item-' + idx).style.display='none';
                        if(autoNext) {{
                            if(idx+1 < wpPosts.length) loadWpPost(idx+1);
                            else alert("End of list!");
                        }}
                    }} else {{ alert("Error: " + d.error); }}
                }});
            }}
        }}
        function importSingleLink() {{
            const url = document.getElementById('single_link_url').value;
            fetch('/import_single_link', {{ method: 'POST', body: JSON.stringify({{url: url}}) }})
            .then(r=>r.json()).then(d=>{{ if(d.success) {{ alert('Imported!'); switchTab('local'); window.location.reload(); }} else alert(d.error); }});
        }}

        window.onload = function() {{ try {{ runUploadWorker(); }} catch(e){{}} }}
    </script>
</head>
<body>
    <div class="header">
        <div class="tab-bar">
            <div id="btn-local" class="tab active" onclick="switchTab('local')">Local Curator</div>
            <div id="btn-enhance" class="tab" onclick="switchTab('enhance')">WP Enhance</div>
            <div id="btn-live" class="tab" onclick="switchTab('live')">SNS Import</div>
        </div>

        <!-- SHARED HEADER AREA -->
        <div class="header-row-top" style="padding: 0 20px;">
            {CONN_PANEL_HTML}
            <div class="conn-panel">
                <span style="font-weight:bold;">Gemini AI:</span>
                <input type="password" id="gemini_key" class="conn-input" placeholder="API Key" value="{GEMINI_KEY}">
                <label class="ai-badge">
                    <input type="checkbox" id="use-ai"> ✨ Enhance
                </label>
            </div>

            <div class="status-area">
                <div id="queue-count" class="queue-count">{QUEUE_COUNT} Queued</div>
                <div id="status-log" class="status-panel">{STATUS_LOG_MSG}</div>
            </div>
        </div>
        
        <div class="header-row-bottom">
            <div class="filter-group">
                <input type="text" id="f_search" class="filter-input" style="width:120px;" placeholder="Search..." value="{F_SEARCH}" onkeydown="handleSearchKey(event)">
                <input type="checkbox" id="f_include_proc" title="Include Processed" {F_INCLUDE_PROC_CHECKED}>
            </div>
            <div class="filter-group">
                <input type="text" id="f_start" class="filter-input" style="width:60px;" placeholder="Start" value="{F_START}">
            </div>
            <div class="filter-group">
                <select id="f_media" class="filter-input" style="width:70px;">
                    <option value="" {SEL_MEDIA_}>All</option>
                    <option value="images" {SEL_MEDIA_IMAGES}>Images</option>
                    <option value="videos" {SEL_MEDIA_VIDEOS}>Videos</option>
                </select>
            </div>
            <div class="stats-box">
                <div class="stat-item"><span id="stat-rem" class="stat-val">{STAT_REMAINING}</span><span class="stat-lbl">Left</span></div>
                <div class="stat-item"><span id="stat-rem-img" class="stat-val">{STAT_REM_IMGS}</span><span class="stat-lbl">Imgs</span></div>
                <div class="stat-item"><span id="stat-rem-vid" class="stat-val">{STAT_REM_VIDS}</span><span class="stat-lbl">Vids</span></div>
                <div class="stat-sep"></div>
                <div class="stat-item"><span id="stat-q-media" class="stat-val" style="color:#31a24c;">{STAT_Q_MEDIA}</span><span class="stat-lbl">Q.Med</span></div>
                <div class="stat-item"><span id="stat-q-size" class="stat-val">{STAT_Q_SIZE}</span><span class="stat-lbl">Size</span></div>
            </div>
            <button class="filter-btn" onclick="applyFilters()">Go</button>
            
            <div class="opts-group">
                <label class="opt-label" style="color: #d93025;">
                    <input type="checkbox" id="force-today"> Force Today
                </label>
                <label class="opt-label">
                    <input type="checkbox" id="auto-process-rest" checked> Auto-Process Rest
                </label>
                <label class="opt-label">
                    <input type="checkbox" id="hide-processed-chk" {HIDE_CHECKED} onchange="applyFilters()"> Hide Processed
                </label>
            </div>
        </div>
    </div>
    
    <!-- TAB: LOCAL CURATOR (Existing) -->
    <div id="local" class="tab-content active">
        <div class="container">
            <div id="posts-wrapper">
                {POSTS_HTML}
            </div>
            <div class="load-more-container">
                <button id="load-more-btn" class="load-more-btn" onclick="loadMorePosts()">Load More Posts</button>
            </div>
        </div>
        <div class="floating-upload">
             <button class="fab-btn fab-upload" onclick="executeBulk('queue')">
                <span>&#8679;</span> Upload Selected
            </button>
        </div>
        <div class="floating-bottom">
            <button class="fab-btn fab-select" onclick="toggleSelectAll()">
                <span>&#9745;</span> Select All
            </button>
            <button class="fab-btn fab-skip" onclick="executeBulk('process')">
                <span>&#10006;</span> Skip Selected
            </button>
        </div>
    </div>

    <!-- TAB: WP ENHANCE -->
    <div id="enhance" class="tab-content">
        <div class="enhance-layout">
            <div class="enhance-sidebar">
                <div style="padding:15px; border-bottom:1px solid #ddd; background:#f7f8fa;">
                    <button id="btn-rolling-toggle" class="btn btn-magic" style="width:100%; margin-bottom:10px;" onclick="toggleRollingMode()">Start Rolling Auto-Pilot</button>
                    
                    <div style="display:flex; align-items:center; gap:5px; font-size:12px;">
                        <input type="checkbox" id="wp-filter-uncat" checked> <label for="wp-filter-uncat">Uncategorized Only</label>
                    </div>
                    <button id="wp-fetch-btn" class="btn btn-primary" style="width:100%; margin-top:5px;" onclick="fetchWpPosts()">Fetch Posts</button>
                </div>
                <div id="wp-post-list" class="enhance-list"></div>
            </div>
            
            <!-- SINGLE VIEW -->
            <div id="enhance-single-view" class="enhance-main">
                <div class="enhance-card">
                    <div class="editor-row"><span class="editor-label">Title</span><input type="text" id="edit-title" class="editor-input"></div>
                    <div class="editor-row"><span class="editor-label">Category</span><select id="edit-category" class="editor-select"></select></div>
                </div>
                <div class="enhance-card">
                    <div style="display:flex; justify-content:space-between; margin-bottom:10px;">
                        <span class="editor-label">Content</span>
                        <button class="btn btn-secondary" style="padding:4px 8px;" onclick="distributeMedia()">Distribute Media</button>
                    </div>
                    <div id="edit-content" class="content-preview" contenteditable="true"></div>
                </div>
                <div class="enhance-actions">
                    <button id="btn-ai" class="btn btn-magic" onclick="runAiEnhance()">✨ Magic Enhance</button>
                    <button id="btn-update" class="btn btn-primary" onclick="updateWpPost(true)">Update & Next</button>
                </div>
            </div>
            
            <!-- ROLLING VIEW -->
            <div id="rolling-container" class="enhance-main" style="display:none;">
                <div class="rolling-controls">
                    <div><b>Rolling Auto-Pilot</b> <span style="font-size:12px; color:#666;">(Updates top item when queue > 5)</span></div>
                    <div>
                         <label><input type="checkbox" id="pause-rolling"> <b>PAUSE</b></label>
                    </div>
                </div>
                <div id="rolling-list"></div>
            </div>
        </div>
    </div>

    <!-- TAB: LIVE IMPORT -->
    <div id="live" class="tab-content">
        <div class="container" style="padding-top:50px; text-align:center;">
            <h2>Import Single SNS Post</h2>
            <p>Paste a Facebook link below. We will try to read the text and image.</p>
            <input type="text" id="single_link_url" class="live-input" style="width:300px; padding:10px;" placeholder="Paste URL">
            <br>
            <button id="import-btn" class="live-btn" onclick="importSingleLink()">Fetch Post</button>
        </div>
    </div>
</body>
</html>
"""

# --- BACKEND ---

class ThreadingServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

def load_credentials():
    if os.path.exists(CREDENTIALS_FILE):
        try:
            with open(CREDENTIALS_FILE, 'r') as f: return json.load(f)
        except: pass
    return {}

def load_processed_state():
    global processed_indices, global_stats
    if os.path.exists(PROCESSED_FILE):
        try:
            with open(PROCESSED_FILE, 'r') as f:
                data = json.load(f)
                if isinstance(data, list):
                    processed_indices = set(data)
                    global_stats = {"posts": 0, "images": 0, "videos": 0}
                else:
                    processed_indices = set(data.get("processed_ids", []))
                    global_stats = data.get("stats", {"posts": 0, "images": 0, "videos": 0})
                print(f"Loaded {len(processed_indices)} processed posts.")
        except: pass

def save_processed_state():
    with open(PROCESSED_FILE, 'w') as f:
        json.dump({"processed_ids": list(processed_indices), "stats": global_stats}, f)

def add_server_log(msg):
    timestamp = datetime.now().strftime('%I:%M:%S')
    line = f"[{timestamp}] {msg}"
    server_log_buffer.append(line)
    if len(server_log_buffer) > 50: server_log_buffer.pop(0)

def fix_encoding(text):
    if not text: return ""
    try: return text.encode('latin1').decode('utf-8')
    except: return text

def linkify(text):
    if not text: return ""
    url_pattern = re.compile(r'(https?://\S+)')
    return url_pattern.sub(r'<a href="\1" target="_blank">\1</a>', text)

def extract_date(post):
    keys = ['timestamp', 'creation_timestamp', 'date']
    ts = 0
    for k in keys:
        if k in post and post[k]: ts = post[k]; break
    if ts == 0: return "Unknown Date", None
    try:
        if ts > 10000000000: ts = ts / 1000
        dt = datetime.fromtimestamp(ts)
        return dt.strftime('%Y-%m-%d %H:%M'), dt
    except: return f"Invalid: {ts}", None

def extract_content(post):
    content = []
    if 'data' in post and isinstance(post['data'], list):
        for item in post['data']:
            if 'post' in item: content.append(fix_encoding(item['post']))
            if 'text' in item: content.append(fix_encoding(item['text']))
    title = ""
    if 'title' in post: title = fix_encoding(post['title'])
    if not content and title: return title, ""
    return fix_encoding("\n\n".join(content)), title

def count_media(post):
    count = 0
    for att in post.get('attachments', []):
        for data in att.get('data', []):
            if 'media' in data: count += 1
    return count

def has_media_type(post, mtype):
    attachments = post.get('attachments', [])
    has_img = False
    has_vid = False
    has_link = False
    for att in attachments:
        for data in att.get('data', []):
            if 'media' in data:
                uri = data['media'].get('uri', '')
                if uri.endswith('.mp4'): has_vid = True
                else: has_img = True
            if 'external_context' in data:
                has_link = True
    if mtype == 'any': return has_img or has_vid or has_link
    if mtype == 'images': return has_img
    if mtype == 'videos': return has_vid
    if mtype == 'links': return has_link
    return False

def generate_smart_title(raw_fb_title, body_text, date_str, attachments):
    generic_patterns = [
        r"shared a link", r"shared a video", r"shared a memory", r"shared a post",
        r"updated (his|her|their) status", r"added a new photo", r"added \d+ new photos",
        r"was at", r"is at", r"shared an event", r"wrote on", r"timeline"
    ]
    is_title_generic = False
    if raw_fb_title:
        for pattern in generic_patterns:
            if re.search(pattern, raw_fb_title, re.IGNORECASE):
                is_title_generic = True
                break
    
    clean_body = re.sub(r'<[^>]+>', '', body_text).replace('\n', ' ').strip()
    
    if (not clean_body or (is_title_generic and clean_body == raw_fb_title)) and attachments:
        for att in attachments:
            for data in att.get('data', []):
                if 'external_context' in data:
                    link_name = data['external_context'].get('name')
                    if link_name: return fix_encoding(link_name)

    if raw_fb_title and not is_title_generic: return raw_fb_title

    if clean_body:
        if is_title_generic and clean_body == raw_fb_title: return date_str
        if len(clean_body) > 60: return clean_body[:60].strip() + "..."
        return clean_body
            
    return date_str

def scrape_facebook_url(url):
    try:
        if '?' in url: url = url.split('?')[0]
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.5'
        })
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
            import_dir = os.path.join(EXPORT_FOLDER_PATH, IMPORTED_MEDIA_DIR)
            if not os.path.exists(import_dir): os.makedirs(import_dir)
            filename = f"imported_{int(datetime.now().timestamp())}.jpg"
            local_full_path = os.path.join(import_dir, filename)
            try:
                with urllib.request.urlopen(image_url, context=ctx, timeout=10) as img_resp, open(local_full_path, 'wb') as out_file:
                    shutil.copyfileobj(img_resp, out_file)
                local_image_path = f"{IMPORTED_MEDIA_DIR}/{filename}" 
            except Exception as e: print(f"Failed to download image: {e}")
        new_post = {
            "timestamp": int(datetime.now().timestamp()),
            "data": [{"post": desc}],
            "title": title,
            "attachments": []
        }
        if local_image_path:
            new_post["attachments"].append({
                "data": [{"media": {"uri": local_image_path, "title": "Imported Image"}}]
            })
        return True, new_post
    except Exception as e:
        return False, str(e)

def call_gemini_ai(text, image_paths, api_key, wp_categories):
    learning_examples = ""
    if os.path.exists(LEARNING_FILE):
        try:
            with open(LEARNING_FILE, 'r') as f:
                learn_data = json.load(f)
                examples = learn_data[-3:] if len(learn_data) > 3 else learn_data
                learning_examples = "Here are examples of my preferred style based on my corrections:\n"
                for ex in examples:
                    learning_examples += f"- Input: {ex.get('text_snippet')} -> Title: {ex.get('title')}, Category: {ex.get('category_name')}\n"
        except: pass

    if not api_key: return "No Key", None, text
    cats_str = ", ".join([f"{c['id']}:{c['name']}" for c in wp_categories])
    clean_text = re.sub(r'<[^>]+>', '', text).strip()
    
    prompt = f"""
    You are a professional blog editor. Suggest a concise, engaging title (no 'AI:' prefix) and the single best category ID.
    Constraints:
    1. Never suggest 'Featured' or 'Uncategorized'.
    2. If no existing category fits, suggest "NEW:CategoryName".
    3. Title should be journalistic style, under 60 chars.
    4. Title must be in the same language as the body text.
    {learning_examples}
    Input Text:
    {clean_text[:3000]} 
    Available Categories (ID:Name):
    {cats_str}
    Output strict JSON: {{ "suggested_title": "Title", "suggested_category_id": 123, "suggested_new_category_name": "Name If No Match" }}
    """
    
    models = ["gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-1.5-flash", "gemini-1.5-flash-001", "gemini-pro", "gemini-1.0-pro"]
    
    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        data = { "contents": [{ "parts": [{"text": prompt}] }] }
        try:
            req = urllib.request.Request(url, method="POST", headers={"Content-Type": "application/json"}, data=json.dumps(data).encode('utf-8'))
            with urllib.request.urlopen(req) as response:
                res_json = json.loads(response.read())
                content = res_json['candidates'][0]['content']['parts'][0]['text']
                content = re.sub(r'```json\n|\n```', '', content).strip()
                result = json.loads(content)
                title = result.get('suggested_title', 'AI Title')
                cat_id = result.get('suggested_category_id')
                if cat_id == -1 or cat_id is None:
                     new_name = result.get('suggested_new_category_name')
                     if new_name: cat_id = f"NEW:{new_name}"
                return title, cat_id, text 
        except Exception as e:
            print(f"Gemini {model} Error: {e}")
            continue 
            
    return "Error: AI Failed", None, text

def call_gemini_batch(posts, api_key, wp_categories):
    cats_str = ", ".join([f"{c['id']}:{c['name']}" for c in wp_categories])
    posts_input = []
    for p in posts:
        posts_input.append({"id": p['id'], "text": p['content'], "current_title": p['title']})
        
    prompt = f"""
    You are a professional blog editor. Analyze these {len(posts)} posts.
    For EACH post, return a JSON object with:
    - "suggested_title": Concise, journalistic title (same lang as text, no prefixes).
    - "suggested_category_id": Best matching ID from the list below. If none fit, use "NEW:CategoryName".
    
    Available Categories: {cats_str}
    
    Input Posts JSON:
    {json.dumps(posts_input, ensure_ascii=False)}
    
    Output strictly a JSON LIST of objects corresponding to inputs.
    """
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    data = { "contents": [{ "parts": [{"text": prompt}] }] }
    
    try:
        req = urllib.request.Request(url, method="POST", headers={"Content-Type": "application/json"}, data=json.dumps(data).encode('utf-8'))
        with urllib.request.urlopen(req) as response:
            res_json = json.loads(response.read())
            content = res_json['candidates'][0]['content']['parts'][0]['text']
            content = re.sub(r'```json\n|\n```', '', content).strip()
            return json.loads(content) 
    except Exception as e:
        print(f"Gemini Batch Error: {e}")
        return []

def wp_api_call(endpoint, method="GET", data=None, creds=None):
    if not creds: creds = load_credentials()
    url = f"{creds.get('wp_url')}/wp-json/wp/v2/{endpoint}"
    auth_str = f"{creds.get('wp_user')}:{creds.get('wp_pass')}"
    auth_b64 = base64.b64encode(auth_str.encode()).decode()
    headers = {"Authorization": f"Basic {auth_b64}", "Content-Type": "application/json"}
    req = urllib.request.Request(url, method=method, headers=headers)
    if data: req.data = json.dumps(data).encode('utf-8')
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    try:
        with urllib.request.urlopen(req, context=ctx) as res:
            return json.loads(res.read())
    except Exception as e:
        return {"error": str(e)}

def wp_upload_media(filepath, wp_url, auth_header):
    filename = os.path.basename(filepath)
    api_url = f"{wp_url}/wp-json/wp/v2/media"
    mime_type, _ = mimetypes.guess_type(filepath)
    if not mime_type: mime_type = 'application/octet-stream'
    try:
        with open(filepath, 'rb') as f: file_data = f.read()
        req = urllib.request.Request(api_url, data=file_data)
        req.add_header("Authorization", auth_header)
        req.add_header("Content-Type", mime_type)
        req.add_header("Content-Disposition", f'attachment; filename="{filename}"')
        ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, context=ctx) as response:
            data = json.loads(response.read())
            return data.get('id'), data.get('source_url')
    except Exception as e:
        add_server_log(f"Media Upload Error: {e}")
        return None, None

def wp_create_post(post_data, wp_url, auth_header):
    api_url = f"{wp_url}/wp-json/wp/v2/posts"
    json_data = json.dumps(post_data).encode('utf-8')
    req = urllib.request.Request(api_url, data=json_data)
    req.add_header("Authorization", auth_header)
    req.add_header("Content-Type", "application/json")
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    with urllib.request.urlopen(req, context=ctx) as response:
        return json.loads(response.read())

def process_single_post_upload(post_idx, wp_url, wp_user, wp_pass, force_today, use_ai, gemini_key, custom_title=None, custom_content=None, custom_category=None):
    post = all_posts[post_idx]
    auth_str = f"{wp_user}:{wp_pass}"
    auth_b64 = base64.b64encode(auth_str.encode()).decode()
    auth_header = f"Basic {auth_b64}"
    
    date_str, dt_obj = extract_date(post)
    iso_date = datetime.now().strftime('%Y-%m-%dT%H:%M:%S') if force_today else (dt_obj.strftime('%Y-%m-%dT%H:%M:%S') if dt_obj else datetime.now().strftime('%Y-%m-%dT%H:%M:%S'))
    
    text, raw_title = extract_content(post)
    final_title = custom_title if custom_title else (raw_title if raw_title else date_str)
    category_id = custom_category if custom_category else None
    
    if use_ai and gemini_key and not custom_title:
        cats = fetch_wp_categories(wp_url, auth_header)
        ai_title, ai_cat, ai_text = call_gemini_ai(text, [], gemini_key, cats)
        final_title = ai_title
        category_id = ai_cat

    if custom_content:
        content_html = custom_content
    else:
        attachments = post.get('attachments', [])
        media_blocks_top = ""
        media_blocks_bottom = ""
        media_count = 0
        featured_media_id = None
        
        for att in attachments:
            for data in att.get('data', []):
                if 'media' in data:
                    uri = data['media'].get('uri', '')
                    if uri:
                        if os.path.isabs(uri): possible_path = uri
                        else: possible_path = os.path.join(EXPORT_FOLDER_PATH, uri)
                        if not os.path.exists(possible_path):
                            fname = os.path.basename(uri)
                            for root, dirs, files in os.walk(EXPORT_FOLDER_PATH):
                                if fname in files: possible_path = os.path.join(root, fname); break
                        
                        if os.path.exists(possible_path):
                            mid, murl = wp_upload_media(possible_path, wp_url, auth_header)
                            if mid:
                                is_video = uri.lower().endswith(('.mp4', '.mov'))
                                if not featured_media_id and not is_video: featured_media_id = mid
                                
                                block = f'<!-- wp:image {{"id":{mid}}} --><figure class="wp-block-image"><img src="{murl}" class="wp-image-{mid}"/></figure><!-- /wp:image -->'
                                if is_video: block = f'<!-- wp:video {{"id":{mid}}} --><figure class="wp-block-video"><video controls src="{murl}"></video></figure><!-- /wp:video -->'
                                
                                if media_count < 5: media_blocks_top += block
                                else: media_blocks_bottom += block
                                media_count += 1

        content_html = media_blocks_top + f"<p>{linkify(html.escape(text))}</p>" + media_blocks_bottom
    
    wp_post = {
        'date': iso_date,
        'status': 'publish',
        'title': final_title,
        'content': content_html,
        'format': 'status'
    }
    if not custom_content and 'featured_media_id' in locals() and featured_media_id: 
         wp_post['featured_media'] = featured_media_id
         
    if category_id: wp_post['categories'] = [category_id]

    try:
        res = wp_create_post(wp_post, wp_url, auth_header)
        return True, {'id': res.get('id'), 'link': res.get('link')}
    except Exception as e:
        return False, str(e)

def load_all_posts(root_folder):
    global all_posts
    json_files = []
    for root, dirs, files in os.walk(root_folder):
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
                items = []
                if isinstance(data, list): items = data
                elif isinstance(data, dict):
                    for v in data.values():
                        if isinstance(v, list): items = v; break
                if items: all_posts.extend(items)
        except: pass
    
    print("Sorting posts...")
    def get_ts(p):
        for k in ['timestamp', 'creation_timestamp', 'date']:
            if k in p and p[k]: return p[k]
        return 0
    all_posts.sort(key=get_ts)
    print(f"Total loaded: {len(all_posts)}")

class CuratorHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers['Content-Length'])
        body = json.loads(self.rfile.read(length))
        
        if self.path == '/api_gemini_enhance_batch':
            creds = load_credentials()
            results = call_gemini_batch(body['posts'], creds.get('gemini_key'), body.get('categories', []))
            self.wfile.write(json.dumps(results).encode())
            return

        if self.path == '/api_upload_post':
            success, result = process_single_post_upload(
                body['id'], body['wp_url'], body['wp_user'], body['wp_pass'], 
                body.get('force_today', False), body.get('use_ai', False), body.get('gemini_key', ''),
                body.get('custom_title'), body.get('custom_content'), body.get('custom_category')
            )
            self.send_response(200)
            self.end_headers()
            if success:
                processed_indices.add(body['id'])
                global_stats['posts'] += 1
                save_processed_state()
                if body['id'] in queued_indices: queued_indices.remove(body['id'])
                add_server_log(f"✓ Uploaded #{body['id']}")
                self.wfile.write(json.dumps({'success': True, 'wp_id': result['id'], 'wp_link': result['link']}).encode())
            else:
                add_server_log(f"❌ Error #{body['id']}: {result}")
                self.wfile.write(json.dumps({'success': False, 'error': result}).encode())
            return
            
        if self.path == '/api_wp_update':
            # Record for learning
            if 'content' in body and 'title' in body:
                snippet = re.sub(r'<[^>]+>', '', body['content']).strip()[:200]
                cat_name = "Uncategorized" # Ideally lookup from cache, but ID is okay for now
                new_learn = {"text_snippet": snippet, "title": body['title'], "category_name": str(body.get('category'))}
                
                current_learn = []
                if os.path.exists(LEARNING_FILE):
                     try:
                         with open(LEARNING_FILE, 'r') as f: current_learn = json.load(f)
                     except: pass
                current_learn.append(new_learn)
                if len(current_learn) > 20: current_learn.pop(0)
                
                with open(LEARNING_FILE, 'w') as f: json.dump(current_learn, f)

            cat_val = body.get('category')
            if cat_val and str(cat_val).startswith('NEW:'):
                new_name = cat_val.split(':', 1)[1]
                res = wp_api_call('categories', 'POST', {'name': new_name})
                if 'id' in res: body['categories'] = [res['id']]
            elif cat_val:
                body['categories'] = [int(cat_val)]
            
            if 'category' in body: del body['category']
            
            res = wp_api_call(f"posts/{body['id']}", "POST", body)
            if 'id' in res:
                self.wfile.write(json.dumps({'success': True}).encode())
            else:
                self.wfile.write(json.dumps({'success': False, 'error': res.get('error')}).encode())
            return

        if self.path == '/api_gemini_enhance':
            res = call_gemini_ai(body['text'], [], load_credentials().get('gemini_key'), body.get('categories', []))
            resp_data = {"suggested_title": res[0], "suggested_category_id": res[1], "ai_text": res[2]}
            self.send_response(200); self.end_headers()
            self.wfile.write(json.dumps(resp_data).encode())
            return
            
        if self.path == '/import_single_link':
            success, res = scrape_facebook_url(body.get('url'))
            if success:
                all_posts.insert(0, res)
                self.wfile.write(json.dumps({'success': True}).encode())
            else:
                self.wfile.write(json.dumps({'success': False, 'error': res}).encode())
            return

        if self.path == '/log_client_message':
            add_server_log(body); self.send_response(200); self.end_headers(); return

    def do_GET(self):
        try:
            parsed = urllib.parse.urlparse(self.path)
            query = urllib.parse.parse_qs(parsed.query)
            
            if parsed.path == '/api_wp_list':
                creds = load_credentials()
                if not creds.get('wp_url'): 
                    self.respond_json({"error": "Missing WP Credentials"})
                    return
                params = "per_page=20&status=publish,draft"
                if 'page' in query: params += f"&page={query['page'][0]}"
                if 'category' in query and query['category'][0] == 'uncategorized':
                    cats = wp_api_call("categories?search=Uncategorized", creds=creds)
                    if isinstance(cats, list) and len(cats) > 0: params += f"&categories={cats[0]['id']}"
                if 'search' in query: params += f"&search={urllib.parse.quote(query['search'][0])}"
                posts = wp_api_call(f"posts?{params}", creds=creds)
                all_cats = wp_api_call("categories?per_page=100", creds=creds)
                self.respond_json({"posts": posts if isinstance(posts, list) else [], "categories": all_cats if isinstance(all_cats, list) else []})
                return
                
            if parsed.path == '/get_status_data':
                creds = load_credentials()
                skipped = max(0, len(processed_indices) - global_stats['posts'])
                
                # Calculate Remaining Stats
                rem_imgs = 0
                rem_vids = 0
                # Calculate Queue Stats
                q_media = 0
                q_size = 0
                
                data = {
                    "queue_count": len(queued_indices),
                    "processed": len(processed_indices),
                    "remaining": len(all_posts) - len(processed_indices),
                    "skipped": skipped,
                    "uploads": global_stats,
                    "logs": server_log_buffer,
                    "gemini_key": creds.get('gemini_key', ''),
                    "rem_images": 0, 
                    "rem_videos": 0,
                    "q_media": 0,
                    "q_size": "0 MB",
                    "years_span": ""
                }
                self.respond_json(data)
                return

            if parsed.path == '/add':
                queued_indices.add(int(query['id'][0]))
                self.respond_json({'count': len(queued_indices)})
                return
            if parsed.path == '/remove':
                idx = int(query['id'][0])
                if idx in queued_indices: queued_indices.remove(idx)
                self.respond_json({'count': len(queued_indices)})
                return
            if parsed.path == '/bulk_queue':
                ids = query['ids'][0].split(',')
                for i in ids: queued_indices.add(int(i))
                self.respond_json({'count': len(queued_indices)})
                return
            if parsed.path == '/mark_processed':
                processed_indices.add(int(query['id'][0]))
                save_processed_state()
                self.respond_json({'status': 'ok'})
                return
            if parsed.path == '/bulk_process':
                ids = query['ids'][0].split(',')
                for i in ids: processed_indices.add(int(i))
                save_processed_state()
                self.respond_json({'status': 'ok'})
                return
            if parsed.path == '/get_queue_ids':
                self.respond_json({'ids': sorted(list(queued_indices))})
                return

            if self.path.startswith('/') and not self.path.startswith('/?'):
                decoded_path = urllib.parse.unquote(self.path.lstrip('/'))
                if decoded_path.lower().endswith(('.jpg', '.jpeg', '.png', '.mp4', '.gif')):
                    fname = os.path.basename(decoded_path)
                    for root, dirs, files in os.walk(EXPORT_FOLDER_PATH):
                        if fname in files:
                            self.serve_file(os.path.join(root, fname))
                            return

            if parsed.path == '/':
                is_ajax = query.get('ajax', ['0'])[0] == '1'
                
                page_num = int(query.get('page', [1])[0])
                hide_processed = query.get('hide', ['1'])[0] == '1'
                f_start = query.get('start', [''])[0]
                f_end = query.get('end', [''])[0]
                f_len = int(query.get('len', [0])[0])
                f_media = query.get('media', [''])[0]
                f_sort = query.get('sort', ['asc'])[0]
                f_search = query.get('search', [''])[0].lower()
                f_include_proc = query.get('inc_proc', ['0'])[0] == '1'
                
                start_dt, end_dt = None, None
                if f_start:
                    try: start_dt = datetime.strptime(f_start, '%Y-%m-%d')
                    except: pass
                if f_end:
                    try: end_dt = datetime.strptime(f_end, '%Y-%m-%d')
                    except: pass

                filtered_list = []
                for i, post in enumerate(all_posts):
                    is_proc = i in processed_indices
                    if hide_processed and is_proc and not f_include_proc: continue
                    
                    text, _ = extract_content(post)
                    if f_search and f_search not in text.lower(): continue
                    if len(text) < f_len: continue
                    if f_media and not has_media_type(post, f_media): continue
                    
                    _, _, ts = extract_date(post)
                    if ts > 0:
                        dt = datetime.fromtimestamp(ts)
                        if start_dt and dt < start_dt: continue
                        if end_dt and dt > end_dt: continue
                    
                    filtered_list.append((i, post))

                if f_sort == 'desc': filtered_list.reverse()
                elif f_sort == 'len_desc': filtered_list.sort(key=lambda x: len(extract_content(x[1])[0]), reverse=True)
                elif f_sort == 'len_asc': filtered_list.sort(key=lambda x: len(extract_content(x[1])[0]))
                elif f_sort == 'media_desc': filtered_list.sort(key=lambda x: count_media(x[1]), reverse=True)
                elif f_sort == 'media_asc': filtered_list.sort(key=lambda x: count_media(x[1]))
                
                # Auto-reset page if out of bounds
                total_pages = math.ceil(len(filtered_list) / POSTS_PER_PAGE)
                if page_num > total_pages and total_pages > 0:
                     page_num = 1
                
                start_idx = (page_num - 1) * POSTS_PER_PAGE
                current_batch = filtered_list[start_idx:start_idx+POSTS_PER_PAGE]
                
                # Add script_inject definition (also here for non-ajax)
                script_inject = """
                <script>
                function goToPage(p) {
                    const params = new URLSearchParams(window.location.search);
                    params.set('page', p);
                    window.location.search = params.toString();
                }
                </script>
                """
                
                posts_html = ""
                for real_idx, post in current_batch:
                    date_str, _ = extract_date(post)
                    text, title = extract_content(post)
                    text_display = linkify(html.escape(text))
                    
                    media_html = '<div class="media-grid">'
                    attachments = post.get('attachments', [])
                    for att in attachments:
                        for data in att.get('data', []):
                            if 'media' in data:
                                uri = data['media'].get('uri', '')
                                if uri:
                                    if uri.endswith('.mp4'): media_html += f'<div class="media-item"><video controls src="{uri}"></video></div>'
                                    else: media_html += f'<div class="media-item"><img src="{uri}" loading="lazy"></div>'
                            if 'external_context' in data:
                                ext = data['external_context']
                                url = ext.get("url")
                                domain, thumb_src = "", ""
                                if url:
                                    try:
                                        domain = urllib.parse.urlparse(url).netloc
                                        thumb_src = f"https://www.google.com/s2/favicons?domain={domain}&sz=128"
                                    except: pass
                                link_name = fix_encoding(ext.get('name', 'Link'))
                                media_html += f'<a href="{url}" target="_blank" class="link-card"><img src="{thumb_src}" class="link-card-thumb"><div class="link-card-content"><span class="link-domain">{domain}</span><div class="link-title">{html.escape(link_name)}</div></div></a>'
                    media_html += '</div>'

                    is_queued = real_idx in queued_indices
                    is_processed = real_idx in processed_indices
                    btn_class = "btn btn-add active" if is_queued else "btn btn-add"
                    btn_text = "Queued ✓" if is_queued else "Add to Queue"
                    post_class = "post"
                    if is_queued: post_class += " queued selected"
                    if is_processed: post_class += " processed"
                    
                    raw_json = json.dumps(post, indent=2)
                    
                    posts_html += f"""
                    <div class="{post_class}" id="post-{real_idx}" onclick="togglePostSelect({real_idx}, event)">
                        <div class="post-header">
                            <div style="display:flex; align-items:center; gap:10px;" class="select-controls">
                                <input type="checkbox" name="post_select" value="{real_idx}" class="select-box" autocomplete="off" onclick="event.stopPropagation()">
                                <div class="range-marker" onclick="handleRangeClick(this, {real_idx}); event.stopPropagation()">&#8597;</div>
                                <div class="date">{date_str}</div>
                            </div>
                            <div style="display:flex; gap:10px; align-items:center;">
                                <button class="btn btn-secondary" style="padding:4px 8px; font-size:11px;" onclick="loadEditorForLocal({real_idx}); event.stopPropagation()">Edit / Enhance</button>
                                <div class="debug-toggle" onclick="toggleDebug({real_idx}); event.stopPropagation()">Raw</div>
                            </div>
                        </div>
                        <div class="title">{title}</div>
                        <div class="text">{text_display}</div>
                        {media_html}
                        <div class="actions">
                            <button class="{btn_class}" onclick="toggleQueue(this, {real_idx}); event.stopPropagation()">{btn_text}</button>
                        </div>
                        <div id="debug-{real_idx}" class="raw-json">{html.escape(raw_json)}</div>
                    </div>
                    """

                if is_ajax:
                    self.respond_json({'html': posts_html})
                else:
                    creds = load_credentials()
                    status_log_msg = "✓ Credentials Loaded." if creds.get('wp_url') else "Credentials Error."
                    conn_html = ""
                    if not creds.get('wp_url'):
                         conn_html = """<div id="conn-inputs" class="conn-panel"><input type="text" id="wp_url" class="conn-input" placeholder="URL"><input type="text" id="wp_user" class="conn-input" placeholder="User"><input type="password" id="wp_pass" class="conn-input" placeholder="Pass"></div>"""
                    else:
                         conn_html = f"""<div class="conn-summary"><span>{creds.get('wp_user')} @ {creds.get('wp_url')}</span></div>"""

                    # Define skipped count safely
                    skipped_count = max(0, len(processed_indices) - global_stats['posts'])
                    
                    # Define date range safely
                    min_ts = float('inf')
                    max_ts = 0
                    # Rough date logic without looping everything again for speed
                    # We can loop only on first load or cache it. For now default to empty.
                    years_span = ""

                    page_html = HTML_TEMPLATE.format(
                        POSTS_HTML=posts_html + script_inject,
                        PAGINATION_HTML="", 
                        QUEUE_COUNT=len(queued_indices),
                        PAGE_NUM=page_num,
                        TOTAL_PAGES=0,
                        TOTAL_POSTS=len(all_posts),
                        FILTERED_COUNT=len(filtered_list),
                        HIDE_CHECKED="checked" if hide_processed else "", 
                        CONN_PANEL_HTML=conn_html,
                        STATUS_LOG_MSG=status_log_msg,
                        F_START=f_start, F_END=f_end, F_LEN=f_len if f_len > 0 else "",
                        SEL_MEDIA_="", SEL_MEDIA_HAS_MEDIA="", SEL_MEDIA_IMAGES="", SEL_MEDIA_VIDEOS="", SEL_MEDIA_LINKS="",
                        SEL_SORT_ASC="", SEL_SORT_DESC="", 
                        F_SEARCH=f_search, F_INCLUDE_PROC_CHECKED="checked" if f_include_proc else "",
                        GEMINI_KEY=creds.get('gemini_key', ''),
                        STAT_PROCESSED=len(processed_indices),
                        STAT_REMAINING=len(all_posts) - len(processed_indices),
                        STAT_SKIPPED=skipped_count,
                        STAT_POSTS_UP=global_stats['posts'],
                        STAT_IMGS_UP=global_stats['images'],
                        STAT_VIDS_UP=global_stats['videos'],
                        STAT_REM_IMGS=0, STAT_REM_VIDS=0, STAT_PCT="0%", STAT_Q_MEDIA=0, STAT_Q_SIZE="0 MB", STAT_YEARS=""
                    )
                    self.send_response(200); self.end_headers(); self.wfile.write(page_html.encode('utf-8'))
        except Exception as e:
            # Fallback Error Page
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"<h1>Server Error</h1><pre>{str(e)}</pre>".encode('utf-8'))
            # print(e) # optional console log

    def respond_json(self, data):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def serve_file(self, path):
        self.send_response(200)
        self.end_headers()
        with open(path, 'rb') as f: self.wfile.write(f.read())

if __name__ == "__main__":
    load_processed_state()
    load_all_posts(EXPORT_FOLDER_PATH)
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    print(f"--- FACEBOOK UPLOADER RUNNING ---")
    print(f"1. Open http://localhost:{PORT}")
    with socketserver.ThreadingTCPServer(("", PORT), CuratorHandler) as httpd:
        webbrowser.open(f"http://localhost:{PORT}")
        httpd.serve_forever()