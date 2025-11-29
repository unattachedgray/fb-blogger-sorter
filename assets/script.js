// Global State
let wpPosts = [];
let wpCategories = [];
let currentWpPost = null;
let isLocalMode = false;
let currentEditorId = null;

// UI Helpers
function switchTab(tabId) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.getElementById('btn-' + tabId).classList.add('active');
    document.getElementById(tabId).classList.add('active');

    localStorage.setItem('fb_curator_active_tab', tabId);

    // Toggle Header Controls
    const localHeader = document.getElementById('header-local-controls');
    const enhanceHeader = document.getElementById('header-enhance-controls');

    if (tabId === 'enhance') {
        if (localHeader) localHeader.style.display = 'none';
        if (enhanceHeader) enhanceHeader.style.display = 'flex';
        if (wpPosts.length === 0) fetchWpPosts();
    } else {
        if (localHeader) localHeader.style.display = 'flex';
        if (enhanceHeader) enhanceHeader.style.display = 'none';
    }
}

function toggleSelectAll() {
    const checkboxes = document.querySelectorAll('.post-check');
    const allChecked = Array.from(checkboxes).every(c => c.checked);

    checkboxes.forEach(c => c.checked = !allChecked);
}

function executeBulk(action) {
    const selected = Array.from(document.querySelectorAll('.post-check:checked')).map(c => c.value);
    if (selected.length === 0) return alert("No items selected!");

    if (action === 'queue') {
        fetch('/bulk_queue?ids=' + selected.join(',')).then(r => r.json()).then(d => {
            alert(`Queued ${d.count} items.`);
            window.location.reload();
        });
    } else if (action === 'process') {
        alert("Bulk Skip not fully implemented yet.");
    }
}

// Worker Loop
function runUploadWorker() {
    setInterval(() => {
        fetch('/get_status_data').then(r => r.json()).then(data => {
            // Update Stats
            document.getElementById('stat-rem').innerText = data.remaining;
            document.getElementById('stat-rem-img').innerText = data.rem_images;
            document.getElementById('stat-rem-vid').innerText = data.rem_videos;
            document.getElementById('stat-q-media').innerText = data.q_media;
            document.getElementById('stat-q-size').innerText = data.q_size;
            document.getElementById('stat-ai-calls').innerText = data.ai_stats.calls;
            document.getElementById('stat-ai-tokens').innerText = data.ai_stats.tokens;

            // Auto-Process Logic
            const autoProcess = document.getElementById('auto-process-rest').checked;
            if (autoProcess && data.queue_count === 0 && data.remaining > 0) {
                // If queue is empty and we have remaining items, maybe add more?
                // For now, we just wait.
            }
        });
    }, 2000);
}

// WP Enhance Logic
async function fetchWpPosts(force = false) {
    const btn = document.getElementById('wp-fetch-btn');
    if (btn) {
        btn.disabled = true;
        btn.innerText = "Fetching...";
    }

    // Check for Uncategorized Only filter
    const uncatCheckbox = document.getElementById('wp-filter-uncat');
    const uncat = uncatCheckbox ? uncatCheckbox.checked : false;

    // Try to load from cache if not forced and not filtered (or handle filtered cache?)
    // For simplicity, only cache the main list (uncat=false or true? Let's cache the default view)
    // Actually, let's just cache the last successful fetch and store the 'uncat' state with it.
    if (!force) {
        const cached = localStorage.getItem('fb_curator_wp_main_list');
        if (cached) {
            try {
                const parsed = JSON.parse(cached);
                // Check if cache matches current filter
                if (parsed.uncat === uncat && parsed.posts && parsed.posts.length > 0) {
                    wpPosts = parsed.posts;
                    wpCategories = parsed.categories || [];
                    logDebug(`Restored ${wpPosts.length} posts from cache.`);
                    renderWpList();

                    // Update stats if in cache
                    if (parsed.total_posts) document.getElementById('wp-stat-total').innerText = parsed.total_posts;
                    if (parsed.total_uncategorized) document.getElementById('wp-stat-uncat').innerText = parsed.total_uncategorized;

                    if (btn) {
                        btn.disabled = false;
                        btn.innerText = "Fetch Posts";
                    }
                    return;
                }
            } catch (e) {
                console.error("Cache parse error", e);
            }
        }
    }

    logDebug(`Fetching WP posts... (Uncategorized: ${uncat})`);

    try {
        const params = new URLSearchParams();
        params.set('per_page', '20');
        if (uncat) params.set('category', 'uncategorized');

        const res = await fetch(`/api_wp_list?${params.toString()}`);
        const data = await res.json();

        wpPosts = data.posts || [];
        wpCategories = data.categories || [];

        // Cache the result
        localStorage.setItem('fb_curator_wp_main_list', JSON.stringify({
            posts: wpPosts,
            categories: wpCategories,
            uncat: uncat,
            total_posts: data.total_posts,
            total_uncategorized: data.total_uncategorized,
            timestamp: Date.now()
        }));

        // Update Stats
        if (data.total_posts !== undefined) {
            const elTotal = document.getElementById('wp-stat-total');
            if (elTotal) elTotal.innerText = data.total_posts;
        }
        if (data.total_uncategorized !== undefined) {
            const elUncat = document.getElementById('wp-stat-uncat');
            if (elUncat) elUncat.innerText = data.total_uncategorized;
        }

        logDebug(`Fetched ${wpPosts.length} posts and ${wpCategories.length} categories.`);
        renderWpList();

        if (btn) {
            btn.disabled = false;
            btn.innerText = "Fetch Posts";
        }

        const sel = document.getElementById('edit-category');
        if (sel) {
            sel.innerHTML = `<option value="">-- Select Category --</option>`;
            wpCategories.forEach(c => {
                sel.innerHTML += `<option value="${c.id}">${c.name}</option>`;
            });
        }
    } catch (e) {
        console.error(e);
        logDebug("WP Fetch Error: " + e);
        if (btn) {
            btn.disabled = false;
            btn.innerText = "Fetch Error";
        }
    }
}

function renderWpList() {
    const list = document.getElementById('wp-post-list');
    if (!list) return;
    list.innerHTML = "";

    wpPosts.forEach(p => {
        const div = document.createElement('div');
        div.className = "enhance-item";
        div.id = "wp-item-" + p.id;
        div.onclick = () => {
            loadWpPost(p.id);
            // Highlight active item
            document.querySelectorAll('.enhance-item').forEach(el => el.classList.remove('active'));
            div.classList.add('active');
        };
        div.innerHTML = `
            <div style="font-weight:600; margin-bottom:4px;">${p.title.rendered}</div>
            <div style="font-size:11px; color:var(--text-muted);">ID: ${p.id}</div>
        `;
        list.appendChild(div);
    });
}

function loadWpPost(id) {
    currentWpPost = wpPosts.find(p => p.id == id);
    if (!currentWpPost) return;

    document.querySelectorAll('.enhance-item').forEach(i => i.classList.remove('active'));
    document.getElementById('wp-item-' + id).classList.add('active');

    document.getElementById('edit-title').value = currentWpPost.title.rendered;
    document.getElementById('edit-content').innerHTML = currentWpPost.content.rendered;

    const sel = document.getElementById('edit-category');
    if (sel && currentWpPost.categories && currentWpPost.categories.length > 0) {
        sel.value = currentWpPost.categories[0];
    }
}

function loadRollingPost(id) {
    // Find in rolling queue
    const item = rollingQueue.find(i => i.original.id == id);
    if (!item) return;

    currentWpPost = item.original;

    // Highlight active item in rolling list
    document.querySelectorAll('.rolling-card').forEach(i => i.classList.remove('active'));
    const card = document.getElementById(item.domId);
    if (card) card.classList.add('active');

    document.getElementById('edit-title').value = item.ai.suggested_title || currentWpPost.title.rendered;
    document.getElementById('edit-content').innerHTML = currentWpPost.content.rendered;

    const sel = document.getElementById('edit-category');
    if (sel) {
        if (item.ai.suggested_category_id) {
            sel.value = item.ai.suggested_category_id;
        } else if (currentWpPost.categories && currentWpPost.categories.length > 0) {
            sel.value = currentWpPost.categories[0];
        } else {
            sel.value = "";
        }
    }
}

async function runAiEnhance() {
    if (!currentWpPost) return alert("No post selected!");

    const btn = document.getElementById('btn-ai');
    const originalText = btn.innerText;
    btn.innerText = "✨ Magic...";
    btn.disabled = true;

    const content = document.getElementById('edit-content').innerText;

    try {
        const res = await fetch('/api_gemini_enhance', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                text: content,
                categories: wpCategories
            })
        });
        const data = await res.json();

        if (data.error) {
            alert("AI Error: " + data.error);
        } else {
            document.getElementById('edit-title').value = data.suggested_title;

            // Select category
            const catSel = document.getElementById('edit-category');
            if (data.suggested_category_id) {
                catSel.value = data.suggested_category_id;
            }

            // Show summary
            const summary = `AI: Set title and suggested category "${data.suggested_category_name || 'Unknown'}"`;
            logDebug(summary);
            alert(summary);
        }
    } catch (e) {
        console.error(e);
        logDebug("AI Enhance Error: " + e);

        // Try to show more info if available
        if (e.message && e.message.includes('<')) {
            alert("AI Enhance Error: The server returned an HTML error page instead of JSON. Check the server console for details. Likely a 500 or 404 error.");
        } else {
            alert("AI Enhance Error: " + e);
        }
    } finally {
        btn.innerText = originalText;
        btn.disabled = false;
    }
}

async function updateAndNext() {
    if (!currentWpPost) return alert("No post selected!");

    const btn = document.getElementById('btn-update-next') || event.target;
    const originalText = btn.innerText;
    btn.innerText = "Updating...";
    btn.disabled = true;

    const title = document.getElementById('edit-title').value;
    const category = document.getElementById('edit-category').value;
    const content = document.getElementById('edit-content').innerHTML;

    try {
        const res = await fetch('/api_wp_update', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                id: currentWpPost.id,
                title: title,
                category: category,
                content: content
            })
        });
        const data = await res.json();

        if (data.status === 'ok') {
            logDebug(`Updated post ${currentWpPost.id}: "${title}"`);

            // Find next uncategorized post
            const currentIndex = wpPosts.findIndex(p => p.id === currentWpPost.id);
            let nextPost = null;

            for (let i = currentIndex + 1; i < wpPosts.length; i++) {
                if (!wpPosts[i].categories || wpPosts[i].categories.length === 0) {
                    nextPost = wpPosts[i];
                    break;
                }
            }

            if (nextPost) {
                loadWpPost(nextPost.id);
                logDebug(`Loaded next post: ${nextPost.id}`);
            } else {
                alert("No more uncategorized posts!");
                logDebug("No more uncategorized posts in list");
            }
        } else {
            alert(`Error: ${data.error || 'Unknown error'}`);
            logDebug(`Update error: ${data.error}`);
        }
    } catch (e) {
        console.error(e);
        logDebug(`Update failed: ${e}`);
        alert(`Update failed: ${e.message}`);
    } finally {
        btn.innerText = originalText;
        btn.disabled = false;
    }
}


// ROLLING LOGIC
let rollingQueue = [];
let rollingActive = false;
let rollingPage = 1;
let isFetchingBatch = false;
let lastFetchTime = 0;
let isUpdatingItem = false;
let rollingInterval = null;

function toggleRollingMode() {
    const singleView = document.getElementById('enhance-single-view');
    const rollingView = document.getElementById('rolling-container');
    const rollingControls = document.getElementById('rolling-controls');
    const statusInd = document.getElementById('rolling-status-indicator');

    if (rollingView.style.display === 'none') {
        // Start Rolling
        singleView.style.display = 'none';
        rollingView.style.display = 'block';
        if (rollingControls) rollingControls.style.display = 'block';
        document.getElementById('btn-rolling-toggle').innerText = "Switch to Single";
        document.getElementById('wp-post-list').style.display = 'none';
        document.getElementById('wp-fetch-btn').style.display = 'none';

        rollingActive = true;
        isFetchingBatch = false; // Reset flag
        isUpdatingItem = false; // Reset flag
        if (statusInd) statusInd.innerText = "RUNNING";

        // Load Sticky Queue
        const savedQueue = localStorage.getItem('fb_curator_rolling_queue');
        let restoredCount = 0;
        if (savedQueue) {
            try {
                const parsed = JSON.parse(savedQueue);
                if (Array.isArray(parsed) && parsed.length > 0) {
                    rollingQueue = parsed;
                    updateRollingListUI();
                    restoredCount = rollingQueue.length;
                    logDebug(`Restored ${restoredCount} items from sticky queue.`);
                }
            } catch (e) {
                console.error("Failed to load sticky queue", e);
            }
        }

        if (restoredCount === 0) {
            logDebug("Starting fresh queue (no sticky items found).");
            fetchRollingBatch();
        } else {
            // If we restored items, don't fetch immediately unless buffer is low
            if (rollingQueue.length < (parseInt(document.getElementById('rolling-buffer-size').value) || 5)) {
                fetchRollingBatch();
            }
        }

        // Start Loop
        if (rollingInterval) clearInterval(rollingInterval);
        rollingInterval = setInterval(processRollingQueue, 2000);
    } else {
        stopRollingMode();
    }
}

function stopRollingMode() {
    rollingActive = false;
    const singleView = document.getElementById('enhance-single-view');
    const rollingView = document.getElementById('rolling-container');
    const rollingControls = document.getElementById('rolling-controls');

    singleView.style.display = 'flex';
    rollingView.style.display = 'none';
    if (rollingControls) rollingControls.style.display = 'none';
    document.getElementById('wp-post-list').style.display = 'block';
    document.getElementById('wp-fetch-btn').style.display = 'block';
    document.getElementById('btn-rolling-toggle').innerText = "Start Rolling Auto-Pilot";

    if (rollingInterval) clearInterval(rollingInterval);
    const statusInd = document.getElementById('rolling-status-indicator');
    if (statusInd) statusInd.innerText = "IDLE";
}

function clearRollingQueue() {
    if (confirm("Clear all items from the rolling queue?")) {
        rollingQueue = [];
        updateRollingListUI();
        saveRollingQueue();
        logDebug("Queue cleared.");
    }
}

function saveRollingQueue() {
    localStorage.setItem('fb_curator_rolling_queue', JSON.stringify(rollingQueue));
}

function removeFromQueue(id) {
    const idx = rollingQueue.findIndex(i => i.original.id == id);
    if (idx > -1) {
        rollingQueue.splice(idx, 1);
        updateRollingListUI();
        saveRollingQueue();
        logDebug("Removed item " + id + " from queue.");
    }
}

function renderRollingCard(item) {
    const container = document.getElementById('rolling-list');
    let catOptions = `<option value="">-- Select --</option>`;
    wpCategories.forEach(c => {
        const selected = (item.ai.suggested_category_id == c.id) ? "selected" : "";
        catOptions += `<option value="${c.id}" ${selected}>${c.name}</option>`;
    });
    catOptions += `<option value="NEW:">-- Create New --</option>`;

    const html = `
    <div class="rolling-card" id="${item.domId}" onclick="loadRollingPost(${item.original.id})">
        <div style="display:flex; justify-content:space-between;" onclick="event.stopPropagation()">
            <input type="checkbox" class="rolling-check" checked id="check-${item.original.id}">
            <button style="border:none; background:none; color:red; cursor:pointer;" onclick="removeFromQueue(${item.original.id})">X</button>
        </div>
        <div class="rolling-content">
            <div class="rolling-status" id="status-${item.original.id}">WAITING IN BUFFER...</div>
            <div class="editor-row" style="margin-bottom:5px;">
                <input type="text" class="editor-input" id="title-${item.original.id}" value="${item.ai.suggested_title}">
            </div>
            <div class="editor-row" style="margin-bottom:5px; display:flex; gap:10px; flex-wrap: wrap;">
                <select class="editor-select" id="cat-${item.original.id}" style="width:140px;" onchange="toggleNewCatInput(${item.original.id}, this)">${catOptions}</select>
                <input type="text" class="editor-input" id="new-cat-${item.original.id}" style="display:none; width:140px;" placeholder="New Category Name">
                <div style="font-size:11px; color:#888; align-self:center;">ID: #${item.original.id}</div>
            </div>
            <div style="font-size:12px; color:#555;">${item.original.content.rendered.replace(/<[^>]+>/g, '').substring(0, 150)}...</div>
        </div>
    </div>
    `;
    container.insertAdjacentHTML('beforeend', html);
}

function updateRollingListUI() {
    const list = document.getElementById('rolling-list');
    list.innerHTML = '';
    rollingQueue.forEach(item => {
        renderRollingCard(item);
    });
}

function toggleNewCatInput(id, select) {
    const input = document.getElementById('new-cat-' + id);
    if (select.value === 'NEW:') {
        input.style.display = 'block';
        input.focus();
    } else {
        input.style.display = 'none';
    }
}

function processRollingQueue() {
    try {
        if (!rollingActive) return;

        const bufferSize = parseInt(document.getElementById('rolling-buffer-size').value) || 5;

        if (isFetchingBatch && (Date.now() - lastFetchTime > 10000)) {
            logDebug("Fetch timed out (>10s), resetting flag.");
            isFetchingBatch = false;
            const list = document.getElementById('rolling-list');
            if (list) list.insertAdjacentHTML('beforeend', '<div style="color:red; font-size:11px;">Fetch timed out, retrying...</div>');
        }

        if (!isUpdatingItem && rollingQueue.length >= bufferSize) {
            const item = rollingQueue[0];
            const checkbox = document.getElementById('check-' + item.original.id);

            if (checkbox && checkbox.checked && !document.getElementById('pause-rolling').checked) {
                updateRollingItem(item);
            } else if (checkbox && !checkbox.checked) {
                rollingQueue.shift();
                saveRollingQueue();
                document.getElementById(item.domId).remove();
            }
        }

        if (rollingQueue.length < bufferSize && !isFetchingBatch) {
            fetchRollingBatch();
        }
    } catch (e) {
        console.error("Loop Error:", e);
        logDebug("Loop Error: " + e.message);
    }
}

function updateRollingItem(item) {
    isUpdatingItem = true;
    const dom = document.getElementById(item.domId);
    dom.classList.add('updating');
    document.getElementById('status-' + item.original.id).innerText = "UPDATING...";
    const statusInd = document.getElementById('rolling-status-indicator');
    if (statusInd) statusInd.innerText = "UPDATING ITEM...";
    logDebug(`Updating item ${item.original.id}...`);

    const title = document.getElementById('title-' + item.original.id).value;
    const catSelect = document.getElementById('cat-' + item.original.id);
    let category = catSelect.value;

    if (category === 'NEW:') {
        category = 'NEW:' + document.getElementById('new-cat-' + item.original.id).value;
    }

    const payload = {
        id: item.original.id,
        title: title,
        category: category,
        content: item.original.content.rendered
    };

    fetch('/api_wp_update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    }).then(r => r.json()).then(d => {
        if (d.status === 'ok') {
            logDebug(`Item ${item.original.id} updated.`);
            rollingQueue.shift();
            saveRollingQueue();
            dom.remove();
            isUpdatingItem = false;
            if (statusInd) statusInd.innerText = "RUNNING";
        } else {
            logDebug(`Error updating item ${item.original.id}: ${d.error}`);
            isUpdatingItem = false;
            if (statusInd) statusInd.innerText = "ERROR";
        }
    }).catch(e => {
        logDebug(`Network error updating item ${item.original.id}: ${e}`);
        isUpdatingItem = false;
        if (statusInd) statusInd.innerText = "NET ERROR";
    });
}

async function fetchRollingBatch() {
    isFetchingBatch = true;
    lastFetchTime = Date.now();
    const statusInd = document.getElementById('rolling-status-indicator');
    if (statusInd) statusInd.innerText = "FETCHING BATCH...";
    logDebug("Fetching rolling batch...");

    // Use the same filter as manual fetch if desired, or specific rolling filter
    const uncat = document.getElementById('rolling-uncat-only').checked;

    const params = new URLSearchParams();
    params.set('per_page', '5');
    params.set('page', rollingPage);
    if (uncat) params.set('category', 'uncategorized');

    try {
        const res = await fetch(`/api_wp_list?${params.toString()}`);
        let data;
        try {
            data = await res.json();
        } catch (jsonErr) {
            const text = await res.text();
            logDebug("Rolling Fetch JSON Error. Response: " + text.substring(0, 100));
            throw new Error("Invalid JSON from server");
        }

        if (data.posts && data.posts.length > 0) {
            logDebug(`Fetched ${data.posts.length} posts for rolling queue.`);
            for (const post of data.posts) {
                // Check if already in queue
                if (rollingQueue.find(i => i.original.id == post.id)) continue;

                // AI Enhance
                const aiRes = await fetch('/api_gemini_enhance', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        text: post.content.rendered.replace(/<[^>]+>/g, ''),
                        categories: wpCategories
                    })
                });

                let aiData;
                try {
                    aiData = await aiRes.json();
                } catch (aiJsonErr) {
                    const aiText = await aiRes.text();
                    logDebug("AI Enhance JSON Error. Response: " + aiText.substring(0, 100));
                    // Skip this item or add without AI? Let's skip to be safe
                    continue;
                }

                const item = {
                    original: post,
                    ai: aiData,
                    domId: 'rolling-' + post.id
                };
                rollingQueue.push(item);
                saveRollingQueue();
                renderRollingCard(item);
            }
            rollingPage++;
        } else {
            logDebug("No more posts to fetch.");
        }
    } catch (e) {
        logDebug("Rolling Fetch Error: " + e);
    } finally {
        isFetchingBatch = false;
        if (statusInd) statusInd.innerText = "RUNNING";
    }
}

function forceResetRolling() {
    rollingActive = false;
    isFetchingBatch = false;
    isUpdatingItem = false;
    rollingQueue = [];
    saveRollingQueue();
    updateRollingListUI();

    stopRollingMode();

    const statusInd = document.getElementById('rolling-status-indicator');
    if (statusInd) statusInd.innerText = "RESET";
    logDebug("Rolling state force reset.");
}

// LOGGING
function log(msg) {
    console.log(msg);
}

function logDebug(msg) {
    const logDiv = document.getElementById('debug-log');
    if (logDiv) {
        const time = new Date().toLocaleTimeString();
        logDiv.innerHTML += `<div>[${time}] ${msg}</div>`;
        logDiv.scrollTop = logDiv.scrollHeight;
    }
    console.log("[DEBUG] " + msg);
}

function copyDebugLog() {
    const logDiv = document.getElementById('debug-log');
    if (logDiv) {
        navigator.clipboard.writeText(logDiv.innerText);
        alert("Log copied to clipboard.");
    }
}

function runDiagnostics() {
    fetch('/api_diagnostics').then(r => r.json()).then(d => {
        logDebug("Diagnostics: " + JSON.stringify(d));
    });
}

// Initialization
window.onload = function () {
    runUploadWorker();
    loadSettings();

    // Attach listeners
    attachSettingsListeners();
};

function loadSettings() {
    const settings = JSON.parse(localStorage.getItem('fb_curator_settings') || '{}');
    if (settings.search) document.getElementById('f_search').value = settings.search;
    if (settings.start) document.getElementById('f_start').value = settings.start;
    if (settings.inc_proc !== undefined) document.getElementById('f_include_proc').checked = settings.inc_proc;
    if (settings.media) document.getElementById('f_media').value = settings.media;
    if (settings.hide_proc !== undefined) document.getElementById('hide-processed-chk').checked = settings.hide_proc;

    // Rolling settings
    if (settings.rolling_uncat !== undefined) {
        const el = document.getElementById('rolling-uncat-only');
        if (el) el.checked = settings.rolling_uncat;
    } else {
        // Default to true if not set
        const el = document.getElementById('rolling-uncat-only');
        if (el) el.checked = true;
    }

    // WP Enhance Uncat Filter
    if (settings.wp_uncat !== undefined) {
        const el = document.getElementById('wp-filter-uncat');
        if (el) el.checked = settings.wp_uncat;
    }

    if (settings.buffer_size) {
        const el = document.getElementById('rolling-buffer-size');
        if (el) el.value = settings.buffer_size;
    }

    // Restore active tab
    const activeTab = localStorage.getItem('fb_curator_active_tab');
    if (activeTab) {
        switchTab(activeTab);
    }

    logDebug("Settings loaded.");
}

function saveSettings() {
    const settings = {
        search: document.getElementById('f_search').value,
        start: document.getElementById('f_start').value,
        inc_proc: document.getElementById('f_include_proc').checked,
        media: document.getElementById('f_media').value,
        hide_proc: document.getElementById('hide-processed-chk').checked,
        rolling_uncat: document.getElementById('rolling-uncat-only') ? document.getElementById('rolling-uncat-only').checked : true,
        wp_uncat: document.getElementById('wp-filter-uncat') ? document.getElementById('wp-filter-uncat').checked : false,
        buffer_size: document.getElementById('rolling-buffer-size') ? document.getElementById('rolling-buffer-size').value : 5
    };
    localStorage.setItem('fb_curator_settings', JSON.stringify(settings));
}

function attachSettingsListeners() {
    const ids = ['f_search', 'f_start', 'f_include_proc', 'f_media', 'hide-processed-chk', 'rolling-uncat-only', 'rolling-buffer-size', 'wp-filter-uncat'];
    ids.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('change', saveSettings);
            el.addEventListener('input', saveSettings);
        }
    });
}
