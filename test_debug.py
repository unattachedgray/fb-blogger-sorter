import curator_config as cfg
import curator_wp as wp_mod
import curator_ai as ai_mod
import sys
import io

def run_diagnostics():
    logs = []
    def log(msg):
        print(msg)
        logs.append(str(msg))

    log("--- DIAGNOSTIC TEST ---")

    # 1. Test WP Connection
    log("\n[1] Testing WordPress Connection...")
    try:
        creds = cfg.load_credentials()
        log(f"URL: {creds.get('wp_url')}")
        log(f"User: {creds.get('wp_user')}")
        
        res = wp_mod.wp_api_call("posts?per_page=1")
        if isinstance(res, list):
            log("SUCCESS: WP API returned a list.")
            if len(res) > 0:
                log(f"First post title: {res[0]['title']['rendered']}")
            else:
                log("List is empty, but connection worked.")
        else:
            log(f"FAILURE: WP API returned: {res}")
    except Exception as e:
        log(f"CRITICAL ERROR (WP): {e}")

    # 2. Test Gemini Connection
    log("\n[2] Testing Gemini AI Connection...")
    try:
        key = creds.get('gemini_key')
        if not key:
            log("FAILURE: No Gemini Key found in credentials.")
        else:
            log(f"Key found (starts with {key[:5]}...)")
            test_prompt = "Reply with 'Hello' if you can hear me."
            log(f"Sending prompt: {test_prompt}")
            
            try:
                # ai_mod.call_gemini_ai expects (text, images, key, history)
                ai_res = ai_mod.call_gemini_ai(test_prompt, [], key, [])
                log(f"AI Response: {ai_res}")
                if ai_res and len(ai_res) > 0:
                    log("SUCCESS: Gemini responded.")
                else:
                    log("FAILURE: Gemini returned empty list.")
            except Exception as e:
                log(f"CRITICAL ERROR (AI): {e}")

    except Exception as e:
        log(f"CRITICAL ERROR (General): {e}")

    # 3. Test Local Data
    log("\n[3] Testing Local Data...")
    try:
        import curator_data as data_mod
        log(f"Loaded Posts: {len(data_mod.all_posts)}")
        log(f"Queued Posts: {len(data_mod.queued_indices)}")
        log(f"Processed Posts: {len(data_mod.processed_indices)}")
    except Exception as e:
        log(f"CRITICAL ERROR (Data): {e}")

    log("\n--- END DIAGNOSTIC ---")
    return logs

if __name__ == "__main__":
    run_diagnostics()
