// Global State
let wpPosts = [];
let wpCategories = [];
let currentWpPost = null;
let rollingQueue = [];
let isFetchingBatch = false;
let isUpdatingItem = false;
let rollingPage = 1;
let bufferSize = 5;
let lastFetchTime = 0;
let geminiKey = "";

function switchTab(tabId) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.getElementById('btn-' + tabId).classList.add('active');
    document.getElementById(tabId).classList.add('active');

    // Toggle Header Controls
    const localControls = document.getElementById('header-local-controls');
    const enhanceControls = document.getElementById('header-enhance-controls');

    if (tabId === 'local') {
        if (localControls) localControls.style.display = 'flex';
        if (enhanceControls) enhanceControls.style.display = 'none';
    } else if (tabId === 'enhance') {
        if (localControls) localControls.style.display = 'none';
        if (enhanceControls) enhanceControls.style.display = 'flex';

        const fetchOnStartup = document.getElementById('setting-fetch-startup') ? document.getElementById('setting-fetch-startup').checked : true;
        if (wpPosts.length === 0 && fetchOnStartup) {
            fetchWpPosts();
        }
    } else {
        // Live tab or others
        if (localControls) localControls.style.display = 'none';
        if (enhanceControls) enhanceControls.style.display = 'none';
    }

    saveState();
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
    // setInterval(() => {
    //     fetch('/get_status_data').then(r => r.json()).then(data => {
    //         // Update Stats
    //         document.getElementById('stat-rem').innerText = data.remaining;
    //         document.getElementById('stat-rem-img').innerText = data.rem_images;
    //         document.getElementById('stat-rem-vid').innerText = data.rem_videos;
    //         document.getElementById('stat-q-media').innerText = data.q_media;
    //         document.getElementById('stat-q-size').innerText = data.q_size;
    //         document.getElementById('stat-ai-calls').innerText = data.ai_stats.calls;
    //         document.getElementById('stat-ai-tokens').innerText = data.ai_stats.tokens;
    //         if (data.gemini_key) geminiKey = data.gemini_key;

    //         // Auto-Process Logic
    //         const autoProcess = document.getElementById('auto-process-rest').checked;
    //         if (autoProcess && data.queue_count === 0 && data.remaining > 0) {
    //             // If queue is empty and we have remaining items, maybe add more?
    //             // For now, we just wait.
    //         }
    //     });
    // }, 2000);
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
    saveSettings(); // Save filter state

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
                    logToServer(`Restored ${wpPosts.length} posts from cache.`);
                    renderWpList();

                    // Restore Queue if saved
                    if (window.savedQueueIds) {
                        window.savedQueueIds.forEach(id => addToRollingQueue(id));
                        window.savedQueueIds = null; // Clear after restore
                    }

                    // Update stats if in cache
                    if (parsed.total_posts) {
                        const elTotal = document.getElementById('wp-stat-total');
                        if (elTotal) elTotal.innerText = parsed.total_posts;
                        const elTotalH = document.getElementById('wp-stat-total-header');
                        if (elTotalH) elTotalH.innerText = parsed.total_posts;
                    }
                    if (parsed.total_uncategorized) {
                        const elUncat = document.getElementById('wp-stat-uncat');
                        if (elUncat) elUncat.innerText = parsed.total_uncategorized;
                        const elUncatH = document.getElementById('wp-stat-uncat-header');
                        if (elUncatH) elUncatH.innerText = parsed.total_uncategorized;
                    }

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
    logToServer(`Fetching WP posts... (Uncategorized: ${uncat})`);
    console.log("Starting fetchWpPosts...");

    try {
        const params = new URLSearchParams();
        params.set('per_page', '20');
        if (uncat) params.set('category', 'uncategorized');

        logToServer("Calling /api_wp_list...");

        // 15s Timeout
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 15000);

        try {
            const res = await fetch(`/api_wp_list?${params.toString()}`, { signal: controller.signal });
            clearTimeout(timeoutId);

            const text = await res.text();
            let data;
            try {
                data = JSON.parse(text);
            } catch (jsonErr) {
                logDebug("WP List JSON Error. Response: " + text.substring(0, 100));
                logToServer("WP List JSON Error: " + text.substring(0, 100));
                throw new Error("Invalid JSON from server");
            }

            wpPosts = data.posts || [];
            wpCategories = data.categories || [];

            logToServer(`Fetched ${wpPosts.length} posts and ${wpCategories.length} categories.`);

            // Restore Queue if saved (and not cached path)
            if (window.savedQueueIds) {
                window.savedQueueIds.forEach(id => addToRollingQueue(id));
                window.savedQueueIds = null;
            }

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
            populateCategories();

            // Auto-trigger Batch Optimization in background
            runBatchOptimize(true);

            if (btn) {
                btn.disabled = false;
                btn.innerText = "Fetch Posts";
            }
        } catch (fetchErr) {
            if (fetchErr.name === 'AbortError') {
                throw new Error("Fetch timed out after 15 seconds.");
            }
            throw fetchErr;
        }
    } catch (e) {
        console.error(e);
        logDebug("WP Fetch Error: " + e.message);
        logToServer("WP Fetch Error: " + e.message);
        alert("Fetch Error: " + e.message);
        if (btn) {
            btn.disabled = false;
            btn.innerText = "Fetch Error";
        }
    }
}

function populateCategories() {
    const datalist = document.getElementById('category-list');
    if (!datalist) return;

    datalist.innerHTML = '';
    wpCategories.forEach(cat => {
        const option = document.createElement('option');
        option.value = cat.name;
        option.setAttribute('data-id', cat.id);
        datalist.appendChild(option);
    });
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

    const input = document.getElementById('edit-category');
    if (input && currentWpPost.categories && currentWpPost.categories.length > 0) {
        // Find category name from ID
        const catId = currentWpPost.categories[0];
        const cat = wpCategories.find(c => c.id == catId);
        if (cat) input.value = cat.name;
    } else if (input) {
        input.value = '';
    }

    document.getElementById('enhance-single-view').style.display = 'flex';
    document.getElementById('wp-fetch-container').style.display = 'none';
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

    const btn = document.getElementById('btn-ai-header');
    const originalText = btn.innerText;
    btn.innerText = "✨ Magic...";
    btn.disabled = true;

    const content = document.getElementById('edit-content').innerText;

    try {
        logToServer("Manual AI Enhance started...");
        const res = await fetch('/api_gemini_enhance', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                text: content,
                categories: wpCategories,
                gemini_key: geminiKey
            })
        });
        const data = await res.json();

        if (data.error) {
            alert("AI Error: " + data.error);
            logToServer("AI Error: " + data.error);
        } else {
            document.getElementById('edit-title').value = data.suggested_title;

            // Select category
            const catSel = document.getElementById('edit-category');
            if (data.suggested_category_id) {
                catSel.value = data.suggested_category_id;
            }

            // Update Stats
            if (data.ai_stats) {
                const elCalls = document.getElementById('stat-ai-calls');
                if (elCalls) elCalls.innerText = data.ai_stats.calls;
                const elTokens = document.getElementById('stat-ai-tokens');
                if (elTokens) elTokens.innerText = data.ai_stats.tokens;
            }

            // Show summary
            const summary = `AI: Set title and suggested category "${data.suggested_category_name || 'Unknown'}"`;
            logDebug(summary);
            logToServer(summary);
        }
    } catch (e) {
        console.error(e);
        logDebug("AI Enhance Error: " + e);
        logToServer("AI Enhance Error: " + e);

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

let isBatchRunning = false;

async function runBatchOptimize(isAuto = false) {
    if (isBatchRunning) return;
    isBatchRunning = true;

    const btn = document.getElementById('btn-batch-ai');
    if (btn) {
        btn.disabled = true;
        btn.innerText = "Processing...";
    }

    try {
        // 1. Identify Target Posts (Uncategorized & Visible)
        const targets = wpPosts.filter(p => {
            if (p.categories && p.categories.length > 0) return false;
            const titleInput = document.getElementById('title-' + p.id);
            if (titleInput && titleInput.value !== p.title.rendered) return false;
            if (p.ai_suggestion) return false;
            return true;
        });

        if (targets.length === 0) {
            if (!isAuto) alert("No uncategorized posts found to optimize.");
            return;
        }

        const BATCH_SIZE = 5;
        const MAX_CONCURRENT = 2;
        let processedCount = 0;

        logDebug(`Starting Batch Optimization for ${targets.length} posts...`);

        // Helper to process a chunk
        const processChunk = async (chunk) => {
            chunk.forEach(p => {
                const el = document.getElementById('wp-item-' + p.id);
                if (el) el.style.opacity = '0.5';
            });

            try {
                const res = await fetch('/api_ai_batch', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        posts: chunk.map(p => ({ id: p.id, content: p.content.rendered, title: p.title.rendered })),
                        categories: wpCategories,
                        gemini_key: geminiKey
                    })
                });
                const data = await res.json();

                if (data.results) {
                    Object.keys(data.results).forEach(pid => {
                        const resItem = data.results[pid];
                        if (resItem && !resItem.error) {
                            const post = wpPosts.find(p => p.id == pid);
                            if (post) {
                                post.ai_suggestion = resItem;
                                const el = document.getElementById('wp-item-' + pid);
                                if (el) {
                                    el.style.opacity = '1';
                                    el.style.borderLeft = '4px solid #28a745';
                                    el.querySelector('.wp-title').innerText = "✨ " + resItem.suggested_title;
                                }
                            }
                        }
                    });
                }

                if (data.ai_stats) {
                    const elCalls = document.getElementById('stat-ai-calls');
                    if (elCalls) elCalls.innerText = data.ai_stats.calls;
                    const elTokens = document.getElementById('stat-ai-tokens');
                    if (elTokens) elTokens.innerText = data.ai_stats.tokens;
                }

            } catch (e) {
                console.error("Batch Chunk Error:", e);
                logDebug("Batch Chunk Error: " + e);
            } finally {
                chunk.forEach(p => {
                    const el = document.getElementById('wp-item-' + p.id);
                    if (el) el.style.opacity = '1';
                });
            }
        };

        for (let i = 0; i < targets.length; i += BATCH_SIZE * MAX_CONCURRENT) {
            const promises = [];
            for (let j = 0; j < MAX_CONCURRENT; j++) {
                const start = i + (j * BATCH_SIZE);
                const chunk = targets.slice(start, start + BATCH_SIZE);
                if (chunk.length > 0) {
                    promises.push(processChunk(chunk));
                }
            }
            await Promise.all(promises);
            processedCount += promises.reduce((acc, _, idx) => acc + targets.slice(i + (idx * BATCH_SIZE), i + ((idx + 1) * BATCH_SIZE)).length, 0);
            if (btn) btn.innerText = `Processing... (${Math.min(processedCount, targets.length)}/${targets.length})`;
        }

        logDebug("Batch Optimization Complete.");
        if (!isAuto) alert("Batch Optimization Complete!");

    } catch (e) {
        console.error(e);
        if (!isAuto) alert("Batch Error: " + e);
    } finally {
        isBatchRunning = false;
        if (btn) {
            btn.disabled = false;
            btn.innerText = "🚀 Batch Optimize";
        }
    }
}

async function updateAndNext() {
    if (!currentWpPost) return alert("No post selected!");

    const btn = document.getElementById('btn-update-next') || event.target;
    const originalText = btn.innerText;
    btn.innerText = "Updating...";
    btn.disabled = true;

    const title = document.getElementById('edit-title').value;
    const categoryInput = document.getElementById('edit-category').value;
    const content = document.getElementById('edit-content').innerHTML;

    // Handle category - find ID from name or use NEW: prefix
    let category = categoryInput;
    if (categoryInput) {
        const existingCat = wpCategories.find(c => c.name === categoryInput);
        if (existingCat) {
            category = existingCat.id.toString();
        } else {
            // Custom category - backend handles NEW: prefix
            category = "NEW:" + categoryInput;
        }
    }

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
            logDebug(`Updated post ${currentWpPost.id}: \"${title}\"`);

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
let rollingActive = false;
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
        document.getElementById('wp-fetch-container').style.display = 'none';

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
    document.getElementById('wp-fetch-container').style.display = 'block';
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
    <div class="rolling-card" id="${item.domId}">
        <div style="display:flex; justify-content:space-between;">
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
    </div>`;

    container.insertAdjacentHTML('beforeend', html);
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

        const bufferEl = document.getElementById('rolling-buffer-size');
        const bufferSize = bufferEl ? (parseInt(bufferEl.value) || 5) : 5;

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
        isUpdatingItem = false;
        if (statusInd) statusInd.innerText = "NET ERROR";
    });
}

function logToServer(msg) {
    // Send log to server console
    fetch('/log_client_message', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(msg)
    }).catch(e => console.error("Log to server failed", e));
}

async function fetchRollingBatch() {
    isFetchingBatch = true;
    lastFetchTime = Date.now();
    const statusInd = document.getElementById('rolling-status-indicator');
    if (statusInd) statusInd.innerText = "FETCHING BATCH...";
    logDebug("Fetching rolling batch...");
    logToServer("Fetching rolling batch...");

    // Use the same filter as manual fetch if desired, or specific rolling filter
    const uncat = document.getElementById('rolling-uncat-only') ? document.getElementById('rolling-uncat-only').checked : true;

    const params = new URLSearchParams();
    params.set('per_page', '5');
    params.set('page', rollingPage);
    if (uncat) params.set('category', 'uncategorized');

    // Ensure Key exists before starting
    if (!geminiKey) {
        try {
            logToServer("Key missing, attempting fetch...");
            const statusRes = await fetch('/get_status_data');
            const statusData = await statusRes.json();
            if (statusData.gemini_key) geminiKey = statusData.gemini_key;
            logDebug(`Fetched missing Gemini Key: ${!!geminiKey}`);
            logToServer(`Fetched missing Gemini Key: ${!!geminiKey}`);
        } catch (e) {
            logDebug("Failed to fetch missing key: " + e);
            logToServer("Failed to fetch missing key: " + e);
        }
    }

    try {
        logToServer("Calling WP API...");
        const res = await fetch(`/api_wp_list?${params.toString()}`);
        const text = await res.text();
        let data;
        try {
            data = JSON.parse(text);
        } catch (jsonErr) {
            logDebug("Rolling Fetch JSON Error. Response: " + text.substring(0, 100));
            logToServer("Rolling Fetch JSON Error: " + text.substring(0, 100));
            throw new Error("Invalid JSON from server");
        }

        if (data.posts && data.posts.length > 0) {
            logDebug(`Fetched ${data.posts.length} posts for rolling queue.`);
            logToServer(`Fetched ${data.posts.length} posts.`);

            // Update categories if available
            if (data.categories && data.categories.length > 0) {
                wpCategories = data.categories;
            }

            for (const post of data.posts) {
                // Check if already in queue
                if (rollingQueue.find(i => i.original.id == post.id)) continue;

                // AI Enhance
                let aiData = null;

                if (geminiKey) {
                    try {
                        logToServer(`Enhancing post ${post.id}...`);
                        const aiRes = await fetch('/api_gemini_enhance', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                text: post.content.rendered.replace(/<[^>]+>/g, ''),
                                categories: wpCategories,
                                gemini_key: geminiKey
                            })
                        });

                        const aiText = await aiRes.text();
                        if (!aiRes.ok) {
                            logDebug(`AI Enhance HTTP Error: ${aiRes.status} ${aiRes.statusText}. Body: ${aiText.substring(0, 50)}`);
                            logToServer(`AI Enhance HTTP Error: ${aiRes.status}`);
                        } else if (!aiText || aiText.trim() === "") {
                            logDebug("AI Enhance Error: Empty response from server.");
                            logToServer("AI Enhance Error: Empty response");
                        } else {
                            try {
                                aiData = JSON.parse(aiText);
                                logToServer("AI Enhance Success");
                            } catch (aiJsonErr) {
                                logDebug("AI Enhance JSON Error. Response: " + aiText.substring(0, 100));
                                logToServer("AI Enhance JSON Error");
                            }
                        }
                    } catch (netErr) {
                        logDebug("AI Enhance Network Error: " + netErr);
                        logToServer("AI Enhance Network Error: " + netErr);
                    }
                } else {
                    logDebug("Skipping AI: No Gemini Key available.");
                    logToServer("Skipping AI: No Key");
                }

                // Fallback if AI failed or no key
                if (!aiData) {
                    aiData = {
                        suggested_title: post.title.rendered,
                        suggested_category_id: (post.categories && post.categories.length > 0) ? post.categories[0] : null
                    };
                }

                if (aiData) {
                    const item = {
                        original: post,
                        ai: aiData,
                        domId: 'rolling-item-' + post.id
                    };
                    rollingQueue.push(item);
                    logDebug(`Added post ${post.id} to rolling queue.`);

                    // Render immediately
                    renderRollingCard(item);
                    saveRollingQueue();
                }
            }
            // Increment page for next batch
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
        // alert("Log copied to clipboard.");
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
    if (settings.search) {
        const el = document.getElementById('filter-search');
        if (el) el.value = settings.search;
    }
    if (settings.inc_proc !== undefined) {
        const el = document.getElementById('filter-inc-proc');
        if (el) el.checked = settings.inc_proc;
    }
    if (settings.hide_proc !== undefined) {
        const el = document.getElementById('hide-checked');
        if (el) el.checked = settings.hide_proc;
    }

    // Rolling settings
    if (settings.rolling_uncat !== undefined) {
        const el = document.getElementById('rolling-uncat-only');
        if (el) el.checked = settings.rolling_uncat;
    } else {
        const el = document.getElementById('rolling-uncat-only');
        if (el) el.checked = true;
    }

    // WP Enhance Uncat Filter  
    if (settings.wp_uncat !== undefined) {
        const el = document.getElementById('wp-filter-uncat');
        if (el) el.checked = settings.wp_uncat;
    } else {
        // Default to true (checked)
        const el = document.getElementById('wp-filter-uncat');
        if (el) el.checked = true;
    }

    if (settings.buffer_size) {
        const el = document.getElementById('rolling-buffer-size');
        if (el) el.value = settings.buffer_size;
    }

    if (settings.fetch_on_startup !== undefined) {
        const el = document.getElementById('setting-fetch-startup');
        if (el) el.checked = settings.fetch_on_startup;
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
        search: document.getElementById('filter-search') ? document.getElementById('filter-search').value : '',
        inc_proc: document.getElementById('filter-inc-proc') ? document.getElementById('filter-inc-proc').checked : false,
        hide_proc: document.getElementById('hide-checked') ? document.getElementById('hide-checked').checked : true,
        rolling_uncat: document.getElementById('rolling-uncat-only') ? document.getElementById('rolling-uncat-only').checked : true,
        wp_uncat: document.getElementById('wp-filter-uncat') ? document.getElementById('wp-filter-uncat').checked : true,
        buffer_size: document.getElementById('rolling-buffer-size') ? document.getElementById('rolling-buffer-size').value : 5,
        fetch_on_startup: document.getElementById('setting-fetch-startup') ? document.getElementById('setting-fetch-startup').checked : true
    };
    localStorage.setItem('fb_curator_settings', JSON.stringify(settings));
}

function attachSettingsListeners() {
    const ids = ['filter-search', 'filter-inc-proc', 'hide-checked', 'rolling-uncat-only', 'rolling-buffer-size', 'wp-filter-uncat', 'setting-fetch-startup'];
    ids.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('change', () => {
                saveSettings();
                if (id === 'filter-search' || id === 'filter-inc-proc' || id === 'hide-checked') {
                    applyFilters();
                }
            });
            if (id === 'filter-search') {
                el.addEventListener('keyup', () => {
                    saveSettings();
                    applyFilters();
                });
            }
        }
    });
}

function applyFilters() {
    const search = document.getElementById('filter-search').value.toLowerCase();
    const incProc = document.getElementById('filter-inc-proc').checked;
    const hideChecked = document.getElementById('hide-checked').checked;

    // Filter Local Posts (if implemented)
    // This part depends on how local posts are stored/rendered. 
    // Assuming 'posts' global variable or similar from previous context, but for now let's just log.
    // Actually, local posts are usually in 'allPosts' or similar. 
    // Since I don't have the full local post logic here, I'll just leave a placeholder or basic DOM filtering.

    // Basic DOM filtering for .post-card elements
    const cards = document.querySelectorAll('.post-card');
    let visibleCount = 0;
    cards.forEach(card => {
        const text = card.innerText.toLowerCase();
        const isProcessed = card.classList.contains('processed');
        const isChecked = card.querySelector('.post-check') ? card.querySelector('.post-check').checked : false;

        let visible = true;
        if (search && !text.includes(search)) visible = false;
        if (!incProc && isProcessed) visible = false;
        if (hideChecked && isChecked) visible = false;

        card.style.display = visible ? 'flex' : 'none';
        if (visible) visibleCount++;
    });

    // Update stats if elements exist
    const statRem = document.getElementById('stat-rem');
    if (statRem) statRem.innerText = visibleCount;
}

// Diagnostics
async function runDiagnostics() {
    logDebug("--- STARTING DIAGNOSTICS ---");

    // 1. Check Key
    logDebug("1. Checking Gemini Key...");
    if (geminiKey) {
        logDebug("   Key Present: YES");
    } else {
        logDebug("   Key Present: NO (Attempting fetch...)");
        try {
            const statusRes = await fetch('/get_status_data');
            const statusData = await statusRes.json();
            if (statusData.gemini_key) {
                geminiKey = statusData.gemini_key;
                logDebug("   Key Fetched: YES");
            } else {
                logDebug("   Key Fetched: NO (Server returned empty)");
            }
        } catch (e) {
            logDebug("   Key Fetch Error: " + e);
        }
    }

    // 2. Check WP Connection
    logDebug("2. Checking WP Connection...");
    try {
        const wpRes = await fetch('/api_wp_list?per_page=1');
        if (wpRes.ok) {
            const wpData = await wpRes.json();
            logDebug(`   WP Status: OK (Fetched ${wpData.posts.length} posts)`);
        } else {
            logDebug(`   WP Status: ERROR (${wpRes.status})`);
        }
    } catch (e) {
        logDebug("   WP Network Error: " + e);
    }

    // 3. Check AI Service
    logDebug("3. Checking AI Service...");
    if (geminiKey) {
        try {
            const aiRes = await fetch('/api_gemini_enhance', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    text: "Hello world test",
                    categories: [],
                    gemini_key: geminiKey
                })
            });
            const aiText = await aiRes.text();
            if (aiRes.ok) {
                logDebug("   AI Status: OK");
                logDebug("   AI Response: " + aiText.substring(0, 50) + "...");
            } else {
                logDebug(`   AI Status: ERROR (${aiRes.status})`);
                logDebug("   AI Body: " + aiText.substring(0, 100));
            }
        } catch (e) {
            logDebug("   AI Network Error: " + e);
        }
    } else {
        logDebug("   AI Skipped (No Key)");
    }

    logDebug("--- DIAGNOSTICS COMPLETE ---");
}

// Initialization
document.addEventListener('DOMContentLoaded', () => {
    loadSettings();
    attachSettingsListeners();
    runUploadWorker();
});

