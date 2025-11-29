import os
import json
import urllib.request
import urllib.error
import re
import google.generativeai as genai
import curator_config as cfg

# Global Stats
ai_stats = {'calls': 0, 'tokens': 0}

def record_learning(text, title, category_name):
    entry = {"text_snippet": text[:200], "title": title, "category_name": str(category_name)}
    data = []
    if os.path.exists(cfg.LEARNING_FILE):
        try:
            with open(cfg.LEARNING_FILE, 'r') as f: data = json.load(f)
        except: pass
    data.append(entry)
    if len(data) > 20: data.pop(0)
    with open(cfg.LEARNING_FILE, 'w') as f: json.dump(data, f)

def call_gemini_ai(text, image_paths, api_key, wp_categories):
    # Fallback for short text to avoid AI errors
    if len(text.strip()) < 50:
        return text.strip(), None, text

    if not api_key: return "No Key", None, text
    
    ai_stats['calls'] += 1
    cats_str = ", ".join([f"{c['id']}:{c['name']}" for c in wp_categories])
    
    prompt = f"""
    Act as a professional blog editor. Your goal is to create an engaging, descriptive title for a blog post based on the provided text.
    Also, select the most appropriate category ID from the list provided.
    
    Text: {text[:3000]}
    Categories: {cats_str}
    
    Rules:
    1. Title should be catchy but accurate. Avoid "Title:" prefix.
    2. Category ID must be an integer from the provided list. If unsure, pick the closest match.
    3. Output strictly valid JSON. No markdown code blocks.
    
    Output JSON: {{ "suggested_title": "...", "suggested_category_id": 123 }}
    """
    
    # Use gemini-1.5-flash
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    data = { "contents": [{ "parts": [{"text": prompt}] }] }
    
    try:
        req = urllib.request.Request(url, method="POST", headers={"Content-Type": "application/json"}, data=json.dumps(data).encode('utf-8'))
        with urllib.request.urlopen(req, timeout=15) as response:
            raw_data = response.read().decode('utf-8')
            print(f"[AI Raw Response] {raw_data[:500]}...") # Debug log

            try:
                res = json.loads(raw_data)
            except json.JSONDecodeError:
                print(f"[AI Error] Failed to parse API response: {raw_data}")
                return "AI Error: API Response Invalid", None, text
            
            # Track Tokens
            if 'usageMetadata' in res:
                ai_stats['tokens'] += res['usageMetadata'].get('totalTokenCount', 0)
            
            if 'candidates' not in res or not res['candidates']:
                print(f"[AI Error] No candidates in response: {res}")
                return "AI Error: No candidates", None, text

            txt = res['candidates'][0]['content']['parts'][0]['text']
            print(f"[AI Content] {txt}") # Debug log
            
            # Robust JSON extraction
            match = re.search(r'\{.*\}', txt, re.DOTALL)
            if match:
                try:
                    j = json.loads(match.group(0))
                    return j.get('suggested_title'), j.get('suggested_category_id'), text
                except json.JSONDecodeError:
                    print(f"[AI Error] Invalid JSON in match: {match.group(0)}")
                    return "AI Error: Invalid JSON", None, text
            else:
                print(f"[AI Error] No JSON found in: {txt}")
                # Fallback: Use AI text as title if short, otherwise error
                if len(txt) < 100: return txt, None, text
                return "AI Error: No JSON found", None, text

    except urllib.error.HTTPError as e:
        err_body = e.read().decode('utf-8')
    entry = {"text_snippet": text[:200], "title": title, "category_name": str(category_name)}
    data = []
    if os.path.exists(cfg.LEARNING_FILE):
        try:
            with open(cfg.LEARNING_FILE, 'r') as f: data = json.load(f)
        except: pass
    data.append(entry)
    if len(data) > 20: data.pop(0)
    with open(cfg.LEARNING_FILE, 'w') as f: json.dump(data, f)

def call_gemini_ai(text, image_paths, api_key, wp_categories):
    # Fallback for short text to avoid AI errors
    if len(text.strip()) < 50:
        return text.strip(), None, text

    if not api_key: return "No Key", None, text
    
    ai_stats['calls'] += 1
    cats_str = ", ".join([f"{c['id']}:{c['name']}" for c in wp_categories])
    
    prompt = f"""
    Act as a professional blog editor. Your goal is to create an engaging, descriptive title for a blog post based on the provided text.
    Also, select the most appropriate category ID from the list provided.
    
    Text: {text[:3000]}
    Categories: {cats_str}
    
    Rules:
    1. Title should be catchy but accurate. Avoid "Title:" prefix.
    2. Category ID must be an integer from the provided list. If unsure, pick the closest match.
    3. Output strictly valid JSON. No markdown code blocks.
    
    Output JSON: {{ "suggested_title": "...", "suggested_category_id": 123 }}
    """
    
    # Use gemini-1.5-flash
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    data = { "contents": [{ "parts": [{"text": prompt}] }] }
    
    try:
        req = urllib.request.Request(url, method="POST", headers={"Content-Type": "application/json"}, data=json.dumps(data).encode('utf-8'))
        with urllib.request.urlopen(req, timeout=15) as response:
            raw_data = response.read().decode('utf-8')
            print(f"[AI Raw Response] {raw_data[:500]}...") # Debug log

            try:
                res = json.loads(raw_data)
            except json.JSONDecodeError:
                print(f"[AI Error] Failed to parse API response: {raw_data}")
                return "AI Error: API Response Invalid", None, text
            
            # Track Tokens
            if 'usageMetadata' in res:
                ai_stats['tokens'] += res['usageMetadata'].get('totalTokenCount', 0)
            
            if 'candidates' not in res or not res['candidates']:
                print(f"[AI Error] No candidates in response: {res}")
                return "AI Error: No candidates", None, text

            txt = res['candidates'][0]['content']['parts'][0]['text']
            print(f"[AI Content] {txt}") # Debug log
            
            # Robust JSON extraction
            match = re.search(r'\{.*\}', txt, re.DOTALL)
            if match:
                try:
                    j = json.loads(match.group(0))
                    return j.get('suggested_title'), j.get('suggested_category_id'), text
                except json.JSONDecodeError:
                    print(f"[AI Error] Invalid JSON in match: {match.group(0)}")
                    return "AI Error: Invalid JSON", None, text
            else:
                print(f"[AI Error] No JSON found in: {txt}")
                # Fallback: Use AI text as title if short, otherwise error
                if len(txt) < 100: return txt, None, text
                return "AI Error: No JSON found", None, text

    except urllib.error.HTTPError as e:
        err_body = e.read().decode('utf-8')
        print(f"[AI HTTP Error] {e.code}: {err_body}")
        return f"AI HTTP Error: {e.code}", None, text
    except Exception as e:
        print(f"[AI Error] {e}")
        return text[:50], None, text # Fallback to text snippet

def optimize_batch(posts, api_key, categories):
    """
    Batch process posts to suggest titles and categories using Gemini 2.5 Flash Lite.
    Expects posts to be a list of dicts with 'id' and 'content'.
    """
    if not api_key: return {}

    try:
        genai.configure(api_key=api_key)
        # Use Flash Lite for speed/cost efficiency
        model = genai.GenerativeModel('gemini-2.5-flash-lite') 
        
        # 1. Structure the input cleanly to save tokens
        # Map strict ID to content, stripping HTML and limiting length
        minimized_posts = {}
        for p in posts:
            # Simple HTML strip (regex is fast enough for this)
            clean_text = re.sub(r'<[^>]+>', '', p.get('content', ''))
            # Limit to ~1500 chars to save tokens while keeping context
            minimized_posts[p['id']] = clean_text[:1500]
        
        prompt = f"""
        You are a WordPress curator. Analyze these posts and assign a category from this list: {categories}.
        Return a JSON object where keys are the Post IDs and values are the optimized data.
        
        Input Data:
        {json.dumps(minimized_posts)}
        
        Required JSON Output Schema:
        {{
          "post_id_1": {{ "suggested_title": "Title", "suggested_category_id": 123, "suggested_category_name": "Category Name" }},
          "post_id_2": {{ "suggested_title": "Title", "suggested_category_id": 456, "suggested_category_name": "Category Name" }}
        }}
        """

        # 2. Enforce JSON mode for reliability
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        
        # Track usage
        ai_stats['calls'] += 1
        if hasattr(response, 'usage_metadata'):
            ai_stats['tokens'] += response.usage_metadata.total_token_count
        
        return json.loads(response.text)
    except Exception as e:
        print(f"Batch AI Error: {e}")
        return {"error": str(e)}