# Development TODO

## Session Summary (2025-11-28)

### ✅ Completed

#### Critical Fixes
- **Fixed JavaScript Syntax Error** - Missing opening backtick on line 12 of `script.js` in CSS injection code was preventing entire script from loading
- **Fixed CSS Loading Issues** - Updated stylesheet timestamp in `index.html` to force browser cache refresh
- **CSS Injection Working** - JavaScript successfully injects critical layout CSS to bypass browser caching issues

#### Git & Version Control
- Initialized git repository
- Set up remote: https://github.com/unattachedgray/fb-blogger-sorter
- Committed and pushed all fixes
- Git credentials configured from `credentials.json` (github-username, github-token)

#### Single Post Update Feature
- **Implemented `updateAndNext()` function** in `script.js`
  - Updates WordPress post with edited title & category via `/api_wp_update` endpoint
  - Automatically loads next uncategorized post after successful update
  - Debug logging for each operation
  - Error handling with user feedback
- **Activated Update & Next button** - Changed from placeholder alert to working function

#### Layout & Styling
- Sidebar fixed at 300px width on left
- Debug log positioned in sidebar bottom
- Main content area on right
- Floating "Magic Enhance" and "Update & Next" buttons properly styled
- Purple magic buttons, blue primary buttons working

### 🚧 Known Issues

1. **Browser Caching** - Very aggressive browser caching requires:
   - Hard refresh (Ctrl+Shift+R) after updates
   - Timestamp parameter changes in `index.html`
   - CSS injection as fallback mechanism

2. **Style.css 404 Errors** - Python server occasionally returns 404 for style.css even when file exists (likely server-side caching)

### 📋 Next Session TODO

#### High Priority
- [ ] **Test Single Post Update** - Verify `updateAndNext()` works with actual WordPress site
  - Test with uncategorized posts
  - Test category assignment
  - Test automatic navigation to next post
  - Verify `/api_wp_update` endpoint is implemented in `fb_curator_main.py`

- [ ] **Rolling Auto-Pilot Feature** (Currently Disabled)
  - User requested NOT to work on this yet
  - Existing code present but needs review
  - Consider removing or documenting as experimental feature

#### Medium Priority
- [ ] **UI Improvements**
  - Add loading indicators for Update & Next button
  - Show success/error toast notifications instead of alerts
  - Add keyboard shortcuts (e.g., Ctrl+Enter to update & next)
  
- [ ] **Sidebar Resizability** (Previously Attempted)
  - Original request was for resizable sidebar
  - CSS `resize` property caused layout issues
  - Consider JavaScript-based drag handle implementation
  
- [ ] **Form Validation**
  - Validate title is not empty before update
  - Warn if category is not selected
  - Prevent duplicate rapid clicks on Update & Next

#### Low Priority
- [ ] **Code Cleanup**
  - Remove debug files (`script.js.broken`, `script_header.txt`)
  - Review and clean up CSS injection vs external stylesheet strategy
  - Consider consolidating all CSS into injection or removing injection entirely once caching resolved

- [ ] **Documentation**
  - Update README.md with setup instructions
  - Document the Update & Next workflow
  - Add screenshots to README

- [ ] **Testing**
  - Test with different browsers
  - Test with very long post lists
  - Test error handling when WordPress is unreachable

### 🔧 Technical Debt

1. **CSS Loading Strategy**
   - Currently using BOTH external stylesheet AND JavaScript injection
   - Should pick one approach and stick with it
   - If keeping injection, expand to include ALL styles
   - If removing injection, solve browser caching permanently

2. **Error Handling**
   - Many functions use generic `alert()` for errors
   - Should implement proper notification system
   - Need better logging for debugging

3. **API Endpoints**
   - Verify all required endpoints exist in `fb_curator_main.py`:
     - `/api_wp_list` ✅ (exists)
     - `/api_wp_update` ❓ (needs verification)
     - `/api_gemini_enhance` ❓ (needs verification)

### 📝 Notes

- **Credentials**: Stored in `credentials.json` (gitignored)
  - `wp_url`, `wp_user`, `wp_pass` - WordPress API
  - `gemini_key` - Google Gemini API  
  - `github-username`, `github-token` - Git push credentials

- **CSS Injection**: Located in `script.js` lines 8-28
  - Injects critical layout styles on page load
  - Ensures sidebar width and button styling work even if stylesheet fails to load

- **Browser Cache Issue**: Root cause of most styling problems
  - Browsers cache `index.html`, `style.css`, and `script.js` aggressively
  - Timestamp query parameters help but not foolproof
  - JavaScript injection serves as failsafe

---

Last Updated: 2025-11-28 20:00 EST
