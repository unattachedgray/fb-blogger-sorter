import urllib.request
import json
import re
import os
import curator_config as cfg

# Global Stats
ai_stats = {"calls": 0, "tokens": 0}

def record_learning(text, title, category_name):
    # Save successful edits to learn style
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

def call_gemini_batch(posts, api_key, wp_categories):
    if not api_key: return []
    
    ai_stats['calls'] += 1
    cats_str = ", ".join([f"{c['id']}:{c['name']}" for c in wp_categories])
    
    results = []
    for p in posts:
        # Short text check for batch
        if len(p['content'].strip()) < 50:
            results.append({ "suggested_title": p['content'].strip()[:50], "suggested_category_id": None })
            continue

        prompt = f"""
        Act as a professional blog editor. Suggest a title and category.
        
        Text: {p['content'][:3000]}
        Categories: {cats_str}
        
        Rules:
        1. Title should be catchy but accurate.
        2. Category ID must be an integer from the provided list.
        3. Output strictly valid JSON. No markdown code blocks.
        
        Output JSON: {{ "suggested_title": "...", "suggested_category_id": 123 }}
        """
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        data = { "contents": [{ "parts": [{"text": prompt}] }] }
        
        try:
            req = urllib.request.Request(url, method="POST", headers={"Content-Type": "application/json"}, data=json.dumps(data).encode('utf-8'))
            with urllib.request.urlopen(req, timeout=15) as response:
                res = json.loads(response.read())
                
                # Track Tokens
                if 'usageMetadata' in res:
                    ai_stats['tokens'] += res['usageMetadata'].get('totalTokenCount', 0)

                txt = res['candidates'][0]['content']['parts'][0]['text']
                
                # Robust JSON extraction
                match = re.search(r'\{.*\}', txt, re.DOTALL)
                if match:
                    try:
                        j = json.loads(match.group(0))
                        results.append({
                            "suggested_title": j.get('suggested_title'),
                            "suggested_category_id": j.get('suggested_category_id')
                        })
                    except:
                         results.append({ "suggested_title": p['title'], "suggested_category_id": None })
                else:
                     results.append({ "suggested_title": p['title'], "suggested_category_id": None })

        except Exception as e:
            print(f"Batch AI Error: {e}")
            results.append({ "suggested_title": p['title'], "suggested_category_id": None })
            
    return results