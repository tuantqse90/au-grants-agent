"""HTML Dashboard served by FastAPI."""

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AU Grants Agent — Dashboard</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; background: #0a0a0a; color: #e0e0e0; }
  a { color: #00ff88; text-decoration: none; }
  a:hover { text-decoration: underline; }

  .header { background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 100%); border-bottom: 2px solid #00ff88; padding: 20px 40px; display: flex; align-items: center; justify-content: space-between; }
  .header h1 { color: #00ff88; font-size: 24px; }
  .header .links a { margin-left: 20px; font-size: 14px; color: #888; }
  .header .links a:hover { color: #00ff88; }

  .container { max-width: 1400px; margin: 0 auto; padding: 20px 40px; }

  .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 30px; }
  .stat-card { background: #141414; border: 1px solid #222; border-radius: 12px; padding: 20px; text-align: center; transition: border-color 0.2s; }
  .stat-card:hover { border-color: #00ff88; }
  .stat-card .value { font-size: 36px; font-weight: bold; color: #00ff88; }
  .stat-card .label { font-size: 13px; color: #888; margin-top: 4px; text-transform: uppercase; letter-spacing: 1px; }

  .section { margin-bottom: 30px; }
  .section h2 { font-size: 18px; color: #00ff88; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid #222; }

  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
  @media (max-width: 900px) { .grid-2 { grid-template-columns: 1fr; } }

  .chart-card { background: #141414; border: 1px solid #222; border-radius: 12px; padding: 20px; }
  .chart-card h3 { font-size: 14px; color: #aaa; margin-bottom: 12px; }

  .bar-row { display: flex; align-items: center; margin-bottom: 6px; font-size: 13px; }
  .bar-label { width: 140px; text-align: right; padding-right: 10px; color: #aaa; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .bar-fill { height: 20px; background: linear-gradient(90deg, #00ff88, #00cc6a); border-radius: 4px; min-width: 2px; transition: width 0.5s ease; }
  .bar-value { margin-left: 8px; color: #00ff88; font-weight: 600; min-width: 30px; }

  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th { text-align: left; padding: 10px 12px; color: #00ff88; border-bottom: 2px solid #00ff88; font-weight: 600; text-transform: uppercase; font-size: 11px; letter-spacing: 1px; }
  td { padding: 10px 12px; border-bottom: 1px solid #1a1a1a; }
  tr:hover td { background: #1a1a1a; }
  .status-open { color: #00ff88; font-weight: 600; }
  .status-closed { color: #666; }
  .urgent { color: #ff4444; font-weight: 600; }

  .source-badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
  .source-nsw { background: #1a2a1a; color: #00ff88; }
  .source-arc { background: #1a1a2a; color: #6688ff; }
  .source-business { background: #2a2a1a; color: #ffaa00; }
  .source-grants { background: #2a1a1a; color: #ff6666; }
  .source-arena { background: #1a2a2a; color: #00cccc; }
  .source-nhmrc { background: #2a1a2a; color: #cc66ff; }

  .crawl-btn { background: #00ff88; color: #000; border: none; padding: 8px 20px; border-radius: 6px; font-weight: 600; cursor: pointer; font-size: 13px; }
  .crawl-btn:hover { background: #00cc6a; }
  .crawl-btn:disabled { background: #333; color: #666; cursor: not-allowed; }

  .loading { text-align: center; padding: 40px; color: #666; }
  .loading .spinner { display: inline-block; width: 24px; height: 24px; border: 3px solid #333; border-top: 3px solid #00ff88; border-radius: 50%; animation: spin 1s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }

  .search-box { width: 100%; padding: 10px 16px; background: #1a1a1a; border: 1px solid #333; border-radius: 8px; color: #e0e0e0; font-size: 14px; margin-bottom: 16px; }
  .search-box:focus { outline: none; border-color: #00ff88; }

  .pagination { display: flex; gap: 8px; justify-content: center; margin-top: 16px; }
  .pagination button { background: #1a1a1a; border: 1px solid #333; color: #aaa; padding: 6px 12px; border-radius: 4px; cursor: pointer; }
  .pagination button.active { border-color: #00ff88; color: #00ff88; }
  .pagination button:hover { border-color: #00ff88; }

  .filters { display: flex; gap: 10px; margin-bottom: 16px; flex-wrap: wrap; }
  .filter-select { background: #1a1a1a; border: 1px solid #333; color: #e0e0e0; padding: 8px 12px; border-radius: 6px; font-size: 13px; }
  .filter-select:focus { outline: none; border-color: #00ff88; }

  .toast { position: fixed; bottom: 20px; right: 20px; background: #00ff88; color: #000; padding: 12px 24px; border-radius: 8px; font-weight: 600; display: none; z-index: 1000; }

  /* Modal */
  .modal-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); z-index: 2000; display: none; align-items: center; justify-content: center; }
  .modal-overlay.active { display: flex; }
  .modal { background: #141414; border: 1px solid #00ff88; border-radius: 12px; width: 90%; max-width: 900px; max-height: 90vh; overflow-y: auto; padding: 30px; position: relative; }
  .modal-close { position: absolute; top: 12px; right: 16px; background: none; border: none; color: #666; font-size: 24px; cursor: pointer; }
  .modal-close:hover { color: #00ff88; }
  .modal h2 { color: #00ff88; font-size: 20px; margin-bottom: 16px; padding-right: 30px; }
  .modal-meta { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 20px; font-size: 13px; }
  .modal-meta .meta-item { background: #1a1a1a; padding: 10px 14px; border-radius: 6px; }
  .modal-meta .meta-label { color: #888; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; }
  .modal-meta .meta-value { color: #e0e0e0; margin-top: 4px; }
  .modal-desc { color: #ccc; font-size: 13px; line-height: 1.6; margin-bottom: 20px; padding: 14px; background: #1a1a1a; border-radius: 6px; max-height: 150px; overflow-y: auto; }

  .propose-section { border-top: 1px solid #222; padding-top: 20px; margin-top: 20px; }
  .propose-section h3 { color: #00ff88; font-size: 16px; margin-bottom: 14px; }
  .propose-form { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 16px; }
  .propose-form input { padding: 10px 14px; background: #1a1a1a; border: 1px solid #333; border-radius: 6px; color: #e0e0e0; font-size: 13px; }
  .propose-form input:focus { outline: none; border-color: #00ff88; }
  .propose-form .refine-row { grid-column: 1 / -1; display: flex; align-items: center; gap: 8px; font-size: 13px; color: #aaa; }
  .propose-form .refine-row input[type="checkbox"] { accent-color: #00ff88; width: 16px; height: 16px; }
  .propose-btn { background: #00ff88; color: #000; border: none; padding: 10px 24px; border-radius: 6px; font-weight: 600; cursor: pointer; font-size: 14px; }
  .propose-btn:hover { background: #00cc6a; }
  .propose-btn:disabled { background: #333; color: #666; cursor: not-allowed; }
  .propose-spinner { display: inline-block; width: 16px; height: 16px; border: 2px solid #666; border-top: 2px solid #000; border-radius: 50%; animation: spin 1s linear infinite; vertical-align: middle; margin-right: 8px; }

  .result-tabs { display: flex; gap: 0; margin-top: 20px; border-bottom: 2px solid #222; }
  .result-tab { padding: 10px 20px; cursor: pointer; font-size: 13px; font-weight: 600; color: #666; border-bottom: 2px solid transparent; margin-bottom: -2px; transition: all 0.2s; }
  .result-tab:hover { color: #aaa; }
  .result-tab.active { color: #00ff88; border-bottom-color: #00ff88; }
  .result-content { display: none; padding: 20px; background: #1a1a1a; border-radius: 0 0 8px 8px; font-size: 13px; line-height: 1.8; color: #ddd; white-space: pre-wrap; max-height: 500px; overflow-y: auto; }
  .result-content.active { display: block; }
  .result-info { display: flex; gap: 16px; margin-top: 12px; font-size: 12px; color: #666; flex-wrap: wrap; }
  .result-info span { background: #1a1a1a; padding: 4px 10px; border-radius: 4px; }

  /* Tracking */
  .track-row { display: flex; gap: 8px; align-items: center; margin-top: 12px; padding-top: 12px; border-top: 1px solid #222; }
  .track-btn { padding: 6px 14px; border-radius: 6px; font-size: 12px; font-weight: 600; cursor: pointer; border: 1px solid #333; background: #1a1a1a; color: #aaa; }
  .track-btn:hover { border-color: #00ff88; color: #00ff88; }
  .track-btn.active { background: #00ff88; color: #000; border-color: #00ff88; }
  .track-btn.untrack { background: #1a1a1a; color: #ff4444; border-color: #ff4444; }
  .priority-select { background: #1a1a1a; border: 1px solid #333; color: #e0e0e0; padding: 6px 8px; border-radius: 6px; font-size: 12px; }
  .interest-badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
  .interest-interested { background: #1a2a1a; color: #00ff88; }
  .interest-applied { background: #1a1a2a; color: #6688ff; }
  .interest-won { background: #1a2a1a; color: #00ff88; }
  .interest-rejected { background: #2a1a1a; color: #ff6666; }
  .interest-lost { background: #2a1a1a; color: #ff6666; }

  /* Settings cards */
  .settings-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
  @media (max-width: 900px) { .settings-grid { grid-template-columns: 1fr; } }
  .settings-card { background: #141414; border: 1px solid #222; border-radius: 12px; padding: 20px; }
  .settings-card h3 { color: #00ff88; font-size: 15px; margin-bottom: 14px; }
  .settings-card label { display: block; font-size: 12px; color: #888; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.5px; }
  .settings-card input, .settings-card select { width: 100%; padding: 8px 12px; background: #1a1a1a; border: 1px solid #333; border-radius: 6px; color: #e0e0e0; font-size: 13px; margin-bottom: 10px; }
  .settings-card input:focus, .settings-card select:focus { outline: none; border-color: #00ff88; }
  .settings-row { display: flex; gap: 10px; align-items: center; }

  /* Comparison */
  .compare-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 16px; }
  .compare-panel { background: #1a1a1a; border: 1px solid #333; border-radius: 8px; padding: 16px; }
  .compare-panel h4 { color: #00ff88; font-size: 13px; margin-bottom: 8px; }
  .compare-panel .content-preview { font-size: 12px; line-height: 1.7; color: #ccc; white-space: pre-wrap; max-height: 400px; overflow-y: auto; }
  .compare-meta { display: flex; gap: 12px; margin-bottom: 8px; font-size: 11px; color: #888; }
  .compare-meta span { background: #141414; padding: 2px 8px; border-radius: 4px; }
</style>
</head>
<body>

<div class="header">
  <h1>AU Grants Agent</h1>
  <div class="links">
    <a href="/docs">API Docs</a>
    <a href="/api/stats">Stats JSON</a>
    <a href="https://github.com/tuantqse90/au-grants-agent" target="_blank">GitHub</a>
  </div>
</div>

<div class="container">
  <!-- Stats Cards -->
  <div class="stats-grid" id="stats-grid">
    <div class="stat-card"><div class="value" id="total-grants">—</div><div class="label">Total Grants</div></div>
    <div class="stat-card"><div class="value" id="open-grants">—</div><div class="label">Open Grants</div></div>
    <div class="stat-card"><div class="value" id="sources-count">—</div><div class="label">Sources</div></div>
    <div class="stat-card"><div class="value" id="urgent-count">—</div><div class="label">Closing 7 Days</div></div>
    <div class="stat-card"><div class="value" id="proposals-count">—</div><div class="label">Proposals</div></div>
    <div class="stat-card"><div class="value" id="tracked-count">—</div><div class="label">Tracked</div></div>
  </div>

  <!-- Charts Row -->
  <div class="grid-2 section">
    <div class="chart-card">
      <h3>Grants by Source</h3>
      <div id="source-chart"></div>
    </div>
    <div class="chart-card">
      <h3>Funding Distribution</h3>
      <div id="funding-chart"></div>
    </div>
  </div>

  <div class="grid-2 section">
    <div class="chart-card">
      <h3>Top Categories</h3>
      <div id="category-chart"></div>
    </div>
    <div class="chart-card">
      <h3>Top Agencies</h3>
      <div id="agency-chart"></div>
    </div>
  </div>

  <!-- Urgent Grants -->
  <div class="section">
    <h2>Urgent — Closing Within 7 Days</h2>
    <div id="urgent-table"><div class="loading"><div class="spinner"></div></div></div>
  </div>

  <!-- Browse Grants -->
  <div class="section">
    <h2>Browse Grants</h2>
    <div class="filters">
      <select class="filter-select" id="filter-status" onchange="loadGrants()">
        <option value="">All Status</option>
        <option value="Open" selected>Open</option>
        <option value="Closed">Closed</option>
      </select>
      <select class="filter-select" id="filter-source" onchange="loadGrants()">
        <option value="">All Sources</option>
      </select>
      <input type="text" class="search-box" id="search-box" placeholder="Search grants..." onkeyup="debounceSearch()" style="flex:1;margin-bottom:0;">
      <button class="crawl-btn" onclick="runCrawl()" id="crawl-btn">Crawl Now</button>
    </div>
    <div id="grants-table"><div class="loading"><div class="spinner"></div></div></div>
    <div class="pagination" id="pagination"></div>
  </div>

  <!-- Tracked Grants -->
  <div class="section">
    <h2>Tracked Grants</h2>
    <div id="tracked-table"><div class="loading"><div class="spinner"></div></div></div>
  </div>

  <!-- Proposal History -->
  <div class="section">
    <h2>Generated Proposals</h2>
    <div id="proposals-table"><div class="loading"><div class="spinner"></div></div></div>
  </div>

  <!-- Settings: Scheduler + Email -->
  <div class="section">
    <h2>Settings</h2>
    <div class="settings-grid">
      <div class="settings-card">
        <h3>Auto-Crawl Scheduler</h3>
        <div style="display:flex;gap:10px;align-items:center;margin-bottom:12px">
          <span id="sched-status" style="font-size:13px;color:#666">Checking...</span>
        </div>
        <label>Crawl Time (UTC)</label>
        <div class="settings-row" style="margin-bottom:10px">
          <input type="number" id="sched-hour" min="0" max="23" value="6" style="width:70px">
          <span style="color:#666">:</span>
          <input type="number" id="sched-minute" min="0" max="59" value="0" style="width:70px">
        </div>
        <div style="display:flex;gap:8px">
          <button class="crawl-btn" onclick="toggleScheduler(true)" id="sched-start-btn" style="font-size:12px;padding:6px 14px">Start Scheduler</button>
          <button class="crawl-btn" onclick="toggleScheduler(false)" style="font-size:12px;padding:6px 14px;background:#1a1a1a;color:#ff4444;border:1px solid #ff4444">Stop</button>
        </div>
      </div>

      <div class="settings-card">
        <h3>Email Notifications</h3>
        <label>SMTP Host</label>
        <input type="text" id="smtp-host" placeholder="smtp.gmail.com">
        <label>SMTP Port</label>
        <input type="number" id="smtp-port" value="587" style="width:100px">
        <label>SMTP User</label>
        <input type="text" id="smtp-user" placeholder="you@gmail.com">
        <label>SMTP Password</label>
        <input type="password" id="smtp-pass" placeholder="App password">
        <label>Send To</label>
        <input type="text" id="smtp-to" placeholder="recipient@example.com">
        <div style="display:flex;gap:8px;margin-top:6px">
          <button class="crawl-btn" onclick="saveEmailConfig()" style="font-size:12px;padding:6px 14px">Save Config</button>
          <button class="crawl-btn" onclick="sendTestEmail()" style="font-size:12px;padding:6px 14px;background:#1a1a1a;color:#00ff88;border:1px solid #00ff88">Send Test</button>
        </div>
      </div>
    </div>
  </div>

  <!-- Crawl History -->
  <div class="section">
    <h2>Crawl History</h2>
    <div id="crawl-history"><div class="loading"><div class="spinner"></div></div></div>
  </div>
</div>

<!-- Grant Detail + Proposal Modal -->
<div class="modal-overlay" id="modal-overlay" onclick="if(event.target===this)closeModal()">
  <div class="modal">
    <button class="modal-close" onclick="closeModal()">&times;</button>
    <h2 id="modal-title">Grant Details</h2>
    <div class="modal-meta" id="modal-meta"></div>
    <div class="modal-desc" id="modal-desc"></div>

    <div class="track-row" id="track-row">
      <button class="track-btn" onclick="trackGrant('interested')">Interested</button>
      <button class="track-btn" onclick="trackGrant('applied')">Applied</button>
      <button class="track-btn" onclick="trackGrant('won')">Won</button>
      <button class="track-btn" onclick="trackGrant('rejected')">Rejected</button>
      <select class="priority-select" id="track-priority" onchange="trackGrant()">
        <option value="0">Normal Priority</option>
        <option value="1">High Priority</option>
        <option value="2">Urgent</option>
      </select>
      <button class="track-btn untrack" onclick="untrackGrant()" id="untrack-btn" style="display:none">Untrack</button>
    </div>

    <div class="propose-section">
      <h3>Generate Proposal</h3>
      <div class="propose-form">
        <input type="text" id="propose-org" placeholder="Organisation name (e.g. NullShift Labs)">
        <input type="text" id="propose-focus" placeholder="Focus area (e.g. AI for healthcare)">
        <div class="refine-row">
          <input type="checkbox" id="propose-refine" checked>
          <label for="propose-refine">Refine proposal (second pass for quality)</label>
        </div>
      </div>
      <div style="display:flex;gap:10px">
        <button class="propose-btn" id="propose-btn" onclick="generateProposal()">Generate Proposal</button>
        <button class="propose-btn" onclick="compareProviders()" style="background:#1a1a1a;color:#00ff88;border:1px solid #00ff88">Compare Providers</button>
      </div>
    </div>

    <div id="compare-result" style="display:none">
      <h3 style="color:#00ff88;font-size:15px;margin-top:20px;margin-bottom:12px">Provider Comparison</h3>
      <div class="compare-grid" id="compare-grid"></div>
    </div>

    <div id="proposal-result" style="display:none">
      <div class="result-tabs">
        <div class="result-tab active" onclick="switchTab('en')">English Proposal</div>
        <div class="result-tab" onclick="switchTab('vi')">Tóm tắt Tiếng Việt</div>
      </div>
      <div class="result-content active" id="tab-en"></div>
      <div class="result-content" id="tab-vi"></div>
      <div class="result-info" id="result-info"></div>
      <div style="margin-top:12px;display:flex;gap:10px" id="download-btns">
        <button class="crawl-btn" onclick="downloadProposal('docx')" style="font-size:12px;padding:6px 14px">Download DOCX</button>
        <button class="crawl-btn" onclick="downloadProposal('pdf')" style="font-size:12px;padding:6px 14px">Download PDF</button>
      </div>
    </div>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
const API = '';
let allGrants = [];
let currentPage = 0;
const PAGE_SIZE = 20;
let searchTimer = null;

async function fetchJSON(url) {
  const r = await fetch(API + url);
  return r.json();
}

function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.style.display = 'block';
  setTimeout(() => t.style.display = 'none', 3000);
}

function sourceClass(s) {
  if (!s) return '';
  if (s.includes('nsw')) return 'source-nsw';
  if (s.includes('arc')) return 'source-arc';
  if (s.includes('business')) return 'source-business';
  if (s.includes('grants.gov')) return 'source-grants';
  if (s.includes('arena')) return 'source-arena';
  if (s.includes('nhmrc')) return 'source-nhmrc';
  return '';
}

function renderBars(containerId, data, maxItems = 10) {
  const el = document.getElementById(containerId);
  const entries = Object.entries(data).slice(0, maxItems);
  const maxVal = Math.max(...entries.map(e => e[1]), 1);
  el.innerHTML = entries.map(([k, v]) => `
    <div class="bar-row">
      <div class="bar-label" title="${k}">${k}</div>
      <div class="bar-fill" style="width: ${(v / maxVal * 100)}%"></div>
      <div class="bar-value">${v.toLocaleString()}</div>
    </div>
  `).join('');
}

async function loadStats() {
  const s = await fetchJSON('/api/stats');
  document.getElementById('total-grants').textContent = s.total_grants.toLocaleString();
  document.getElementById('open-grants').textContent = s.open_grants.toLocaleString();
  document.getElementById('sources-count').textContent = Object.keys(s.sources).length;
  document.getElementById('proposals-count').textContent = s.total_proposals;

  try { const tr = await fetchJSON('/api/tracked'); document.getElementById('tracked-count').textContent = tr.length; } catch(e) { document.getElementById('tracked-count').textContent = '0'; }

  renderBars('source-chart', s.sources);
  renderBars('category-chart', s.top_categories);

  // Populate source filter
  const sel = document.getElementById('filter-source');
  Object.keys(s.sources).forEach(src => {
    const opt = document.createElement('option');
    opt.value = src; opt.textContent = src;
    sel.appendChild(opt);
  });
}

async function loadAnalytics() {
  const a = await fetchJSON('/api/analytics/funding');
  renderBars('funding-chart', a.amount_distribution);
  renderBars('agency-chart', a.top_agencies, 8);

  const t = await fetchJSON('/api/analytics/timeline?days=7');
  document.getElementById('urgent-count').textContent = t.urgent_next_7_days.length;

  const urgentEl = document.getElementById('urgent-table');
  if (t.urgent_next_7_days.length === 0) {
    urgentEl.innerHTML = '<p style="color:#666;padding:10px;">No grants closing in the next 7 days.</p>';
    return;
  }
  urgentEl.innerHTML = `<table>
    <tr><th>ID</th><th>Title</th><th>Closing Date</th><th>Agency</th></tr>
    ${t.urgent_next_7_days.map(g => `
      <tr>
        <td style="color:#666">${g.id}</td>
        <td class="urgent">${g.title}</td>
        <td class="urgent">${g.date}</td>
        <td>${g.agency || ''}</td>
      </tr>
    `).join('')}
  </table>`;
}

async function loadGrants() {
  currentPage = 0;
  const status = document.getElementById('filter-status').value;
  const source = document.getElementById('filter-source').value;
  let url = `/api/grants?limit=500`;
  if (status) url += `&status=${status}`;
  if (source) url += `&source=${source}`;

  allGrants = await fetchJSON(url);
  filterAndRender();
}

function debounceSearch() {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => { currentPage = 0; filterAndRender(); }, 300);
}

function filterAndRender() {
  const q = document.getElementById('search-box').value.toLowerCase();
  let filtered = allGrants;
  if (q) {
    filtered = allGrants.filter(g =>
      (g.title || '').toLowerCase().includes(q) ||
      (g.agency || '').toLowerCase().includes(q) ||
      (g.category || '').toLowerCase().includes(q)
    );
  }

  const start = currentPage * PAGE_SIZE;
  const page = filtered.slice(start, start + PAGE_SIZE);
  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);

  const el = document.getElementById('grants-table');
  if (page.length === 0) {
    el.innerHTML = '<p style="color:#666;padding:10px;">No grants found.</p>';
    document.getElementById('pagination').innerHTML = '';
    return;
  }

  el.innerHTML = `<table>
    <tr><th>Title</th><th>Agency</th><th>Category</th><th>Amount</th><th>Closing</th><th>Status</th><th>Source</th></tr>
    ${page.map(g => {
      let amt = '';
      if (g.amount_min && g.amount_max) amt = '$' + g.amount_min.toLocaleString() + ' – $' + g.amount_max.toLocaleString();
      else if (g.amount_min) amt = '$' + g.amount_min.toLocaleString();
      const sc = g.status === 'Open' ? 'status-open' : 'status-closed';
      return `<tr onclick="openGrantDetail('${g.id}')" style="cursor:pointer">
        <td>${(g.title || '').substring(0, 60)}</td>
        <td>${(g.agency || '').substring(0, 30)}</td>
        <td>${(g.category || '').substring(0, 20)}</td>
        <td style="white-space:nowrap">${amt}</td>
        <td>${g.closing_date || ''}</td>
        <td class="${sc}">${g.status}</td>
        <td><span class="source-badge ${sourceClass(g.source)}">${g.source || ''}</span></td>
      </tr>`;
    }).join('')}
  </table>`;

  // Pagination
  const pagEl = document.getElementById('pagination');
  if (totalPages <= 1) { pagEl.innerHTML = ''; return; }
  let html = '';
  for (let i = 0; i < totalPages && i < 10; i++) {
    html += `<button class="${i === currentPage ? 'active' : ''}" onclick="goPage(${i})">${i + 1}</button>`;
  }
  html += `<span style="color:#666;padding:6px"> (${filtered.length} grants)</span>`;
  pagEl.innerHTML = html;
}

function goPage(p) { currentPage = p; filterAndRender(); }

async function loadCrawlHistory() {
  const d = await fetchJSON('/api/analytics/crawls');
  const el = document.getElementById('crawl-history');
  const stats = d.source_stats;
  if (!stats || Object.keys(stats).length === 0) {
    el.innerHTML = '<p style="color:#666;padding:10px;">No crawl history yet.</p>';
    return;
  }
  el.innerHTML = `<table>
    <tr><th>Source</th><th>Crawls</th><th>Total Found</th><th>New</th><th>Errors</th><th>Avg Duration</th><th>Last Crawl</th></tr>
    ${Object.entries(stats).map(([src, s]) => `
      <tr>
        <td><span class="source-badge ${sourceClass(src)}">${src}</span></td>
        <td>${s.total_crawls}</td>
        <td>${s.total_found.toLocaleString()}</td>
        <td>${s.total_new.toLocaleString()}</td>
        <td style="color:${s.errors > 0 ? '#ff4444' : '#00ff88'}">${s.errors}</td>
        <td>${s.avg_duration}s</td>
        <td style="color:#666">${(s.last_crawl || '').substring(0, 19)}</td>
      </tr>
    `).join('')}
  </table>`;
}

async function runCrawl() {
  const btn = document.getElementById('crawl-btn');
  btn.disabled = true; btn.textContent = 'Crawling...';
  showToast('Crawling all sources...');
  try {
    const r = await fetch(API + '/api/crawl', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({})
    });
    const results = await r.json();
    const total = results.reduce((s, r) => s + r.grants_found, 0);
    const newG = results.reduce((s, r) => s + r.grants_new, 0);
    showToast(`Crawl done! ${total} found, ${newG} new`);
    // Reload everything
    loadStats(); loadAnalytics(); loadGrants(); loadCrawlHistory();
  } catch(e) { showToast('Crawl failed: ' + e.message); }
  btn.disabled = false; btn.textContent = 'Crawl Now';
}

async function loadProposals() {
  const proposals = await fetchJSON('/api/proposals?limit=20');
  const el = document.getElementById('proposals-table');
  if (!proposals || proposals.length === 0) {
    el.innerHTML = '<p style="color:#666;padding:10px;">No proposals generated yet. Click a grant to generate one.</p>';
    return;
  }
  // Fetch grant titles for display
  const grantCache = {};
  for (const p of proposals) {
    if (!grantCache[p.grant_id]) {
      try { grantCache[p.grant_id] = await fetchJSON('/api/grants/' + p.grant_id); } catch(e) { grantCache[p.grant_id] = null; }
    }
  }
  el.innerHTML = `<table>
    <tr><th>Grant</th><th>Organisation</th><th>Focus</th><th>Words</th><th>Model</th><th>Generated</th><th>Actions</th></tr>
    ${proposals.map(p => {
      const g = grantCache[p.grant_id];
      const words = (p.content_en || '').split(/\\s+/).filter(w => w).length;
      const date = (p.generated_at || '').substring(0, 16);
      return `<tr>
        <td style="max-width:250px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${g ? g.title : p.grant_id}">${g ? g.title.substring(0, 40) : p.grant_id.substring(0, 8)}</td>
        <td>${p.org_name || 'N/A'}</td>
        <td>${(p.focus_area || '').substring(0, 20)}</td>
        <td>${words.toLocaleString()}</td>
        <td style="color:#666">${p.model || ''}</td>
        <td style="color:#666">${date}</td>
        <td style="white-space:nowrap">
          <button class="crawl-btn" onclick="viewProposal('${p.id}')" style="font-size:11px;padding:4px 10px;margin-right:4px">View</button>
          <button class="crawl-btn" onclick="window.open('/api/proposals/${p.id}/export?format=docx')" style="font-size:11px;padding:4px 10px;margin-right:4px;background:#1a1a1a;color:#00ff88;border:1px solid #00ff88">DOCX</button>
          <button class="crawl-btn" onclick="window.open('/api/proposals/${p.id}/export?format=pdf')" style="font-size:11px;padding:4px 10px;background:#1a1a1a;color:#00ff88;border:1px solid #00ff88">PDF</button>
        </td>
      </tr>`;
    }).join('')}
  </table>`;
}

async function viewProposal(proposalId) {
  const p = await fetchJSON('/api/proposals/' + proposalId);
  let g;
  try { g = await fetchJSON('/api/grants/' + p.grant_id); } catch(e) { g = null; }
  if (g) {
    currentGrantId = g.id;
    document.getElementById('modal-title').textContent = g.title;
    let amt = 'Not specified';
    if (g.amount_min && g.amount_max) amt = '$' + g.amount_min.toLocaleString() + ' – $' + g.amount_max.toLocaleString();
    else if (g.amount_min) amt = '$' + g.amount_min.toLocaleString();
    document.getElementById('modal-meta').innerHTML = `
      <div class="meta-item"><div class="meta-label">Agency</div><div class="meta-value">${g.agency || 'N/A'}</div></div>
      <div class="meta-item"><div class="meta-label">Category</div><div class="meta-value">${g.category || 'N/A'}</div></div>
      <div class="meta-item"><div class="meta-label">Funding</div><div class="meta-value">${amt}</div></div>
      <div class="meta-item"><div class="meta-label">Closing Date</div><div class="meta-value">${g.closing_date || 'N/A'}</div></div>
    `;
    document.getElementById('modal-desc').textContent = g.description || '';
  } else {
    document.getElementById('modal-title').textContent = 'Proposal ' + proposalId.substring(0, 8);
    document.getElementById('modal-meta').innerHTML = '';
    document.getElementById('modal-desc').textContent = '';
  }
  // Show proposal content directly
  document.getElementById('tab-en').textContent = p.content_en || 'No English content.';
  document.getElementById('tab-vi').textContent = p.summary_vi || 'No Vietnamese summary.';
  const words = (p.content_en || '').split(/\\s+/).filter(w => w).length;
  const viWords = (p.summary_vi || '').split(/\\s+/).filter(w => w).length;
  document.getElementById('result-info').innerHTML = `
    <span>EN: ${words.toLocaleString()} words</span>
    <span>VI: ${viWords.toLocaleString()} words</span>
    <span>Model: ${p.model || 'N/A'}</span>
    <span>Tokens: ${(p.tokens_used || 0).toLocaleString()}</span>
  `;
  currentProposalId = proposalId;
  document.getElementById('proposal-result').style.display = 'block';
  switchTab('en');
  document.getElementById('modal-overlay').classList.add('active');
}

// ── Modal + Proposal ────────────────────────────────
let currentGrantId = null;
let currentProposalId = null;

async function openGrantDetail(grantId) {
  currentGrantId = grantId;
  const g = await fetchJSON('/api/grants/' + grantId);

  document.getElementById('modal-title').textContent = g.title;

  let amt = 'Not specified';
  if (g.amount_min && g.amount_max) amt = '$' + g.amount_min.toLocaleString() + ' – $' + g.amount_max.toLocaleString();
  else if (g.amount_min) amt = '$' + g.amount_min.toLocaleString();

  document.getElementById('modal-meta').innerHTML = `
    <div class="meta-item"><div class="meta-label">Agency</div><div class="meta-value">${g.agency || 'N/A'}</div></div>
    <div class="meta-item"><div class="meta-label">Category</div><div class="meta-value">${g.category || 'N/A'}</div></div>
    <div class="meta-item"><div class="meta-label">Funding</div><div class="meta-value">${amt}</div></div>
    <div class="meta-item"><div class="meta-label">Closing Date</div><div class="meta-value">${g.closing_date || 'N/A'}</div></div>
    <div class="meta-item"><div class="meta-label">Status</div><div class="meta-value" style="color:${g.status==='Open'?'#00ff88':'#666'}">${g.status}</div></div>
    <div class="meta-item"><div class="meta-label">Source</div><div class="meta-value">${g.source || 'N/A'}${g.source_url ? ' <a href="'+g.source_url+'" target="_blank" style="margin-left:6px">↗</a>' : ''}</div></div>
  `;

  const desc = g.description || g.eligibility || 'No description available.';
  document.getElementById('modal-desc').textContent = desc;

  // Reset proposal form state
  document.getElementById('proposal-result').style.display = 'none';
  document.getElementById('compare-result').style.display = 'none';
  document.getElementById('propose-btn').disabled = false;
  document.getElementById('propose-btn').innerHTML = 'Generate Proposal';

  // Load tracking state
  loadTrackingState(grantId);

  document.getElementById('modal-overlay').classList.add('active');
}

function closeModal() {
  document.getElementById('modal-overlay').classList.remove('active');
  currentGrantId = null;
}

async function generateProposal() {
  if (!currentGrantId) return;

  const btn = document.getElementById('propose-btn');
  const orgName = document.getElementById('propose-org').value.trim();
  const focusArea = document.getElementById('propose-focus').value.trim();
  const refine = document.getElementById('propose-refine').checked;

  btn.disabled = true;
  btn.innerHTML = '<span class="propose-spinner"></span>Generating...';
  document.getElementById('proposal-result').style.display = 'none';

  try {
    const resp = await fetch(API + '/api/grants/' + currentGrantId + '/propose', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        org_name: orgName || null,
        focus_area: focusArea || null,
        refine: refine
      })
    });

    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.detail || 'Proposal generation failed');
    }

    const result = await resp.json();

    // Fetch full proposal content
    const proposal = await fetchJSON('/api/proposals/' + result.proposal_id);

    // Show results
    document.getElementById('tab-en').textContent = proposal.content_en || 'No English content generated.';
    document.getElementById('tab-vi').textContent = proposal.summary_vi || 'No Vietnamese summary generated.';

    const words = (proposal.content_en || '').split(/\s+/).filter(w => w).length;
    const viWords = (proposal.summary_vi || '').split(/\s+/).filter(w => w).length;
    document.getElementById('result-info').innerHTML = `
      <span>EN: ${words.toLocaleString()} words</span>
      <span>VI: ${viWords.toLocaleString()} words</span>
      <span>Model: ${proposal.model || 'N/A'}</span>
      <span>Tokens: ${(proposal.tokens_used || 0).toLocaleString()}</span>
    `;

    currentProposalId = result.proposal_id;
    document.getElementById('proposal-result').style.display = 'block';
    switchTab('en');

    // Refresh proposal history
    loadProposals();

    showToast('Proposal generated! ' + words + ' words');

  } catch (e) {
    showToast('Error: ' + e.message);
  }

  btn.disabled = false;
  btn.innerHTML = 'Generate Proposal';
}

function switchTab(tab) {
  document.querySelectorAll('.result-tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.result-content').forEach(c => c.classList.remove('active'));
  if (tab === 'en') {
    document.querySelectorAll('.result-tab')[0].classList.add('active');
    document.getElementById('tab-en').classList.add('active');
  } else {
    document.querySelectorAll('.result-tab')[1].classList.add('active');
    document.getElementById('tab-vi').classList.add('active');
  }
}

function downloadProposal(format) {
  if (!currentProposalId) { showToast('No proposal to download'); return; }
  window.open(API + '/api/proposals/' + currentProposalId + '/export?format=' + format);
}

// ── Tracking ────────────────────────────────────────

let currentTrackingInterest = null;

async function loadTrackingState(grantId) {
  currentTrackingInterest = null;
  try {
    const tracked = await fetchJSON('/api/tracked');
    const found = tracked.find(t => t.tracking.grant_id === grantId);
    if (found) {
      currentTrackingInterest = found.tracking.interest;
      document.getElementById('track-priority').value = found.tracking.priority;
      document.getElementById('untrack-btn').style.display = 'inline-block';
    } else {
      document.getElementById('untrack-btn').style.display = 'none';
    }
  } catch(e) {}
  updateTrackButtons();
}

function updateTrackButtons() {
  document.querySelectorAll('#track-row .track-btn:not(.untrack)').forEach(btn => {
    const interest = btn.textContent.toLowerCase();
    btn.classList.toggle('active', interest === currentTrackingInterest);
  });
}

async function trackGrant(interest) {
  if (!currentGrantId) return;
  if (!interest) interest = currentTrackingInterest || 'interested';
  const priority = parseInt(document.getElementById('track-priority').value);
  try {
    await fetch(API + '/api/grants/' + currentGrantId + '/track', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ interest, priority })
    });
    currentTrackingInterest = interest;
    document.getElementById('untrack-btn').style.display = 'inline-block';
    updateTrackButtons();
    loadTrackedGrants();
    showToast('Grant tracked: ' + interest);
  } catch(e) { showToast('Error: ' + e.message); }
}

async function untrackGrant() {
  if (!currentGrantId) return;
  try {
    await fetch(API + '/api/grants/' + currentGrantId + '/track', { method: 'DELETE' });
    currentTrackingInterest = null;
    document.getElementById('untrack-btn').style.display = 'none';
    updateTrackButtons();
    loadTrackedGrants();
    showToast('Grant untracked');
  } catch(e) { showToast('Error: ' + e.message); }
}

async function loadTrackedGrants() {
  const tracked = await fetchJSON('/api/tracked');
  const el = document.getElementById('tracked-table');
  if (!tracked || tracked.length === 0) {
    el.innerHTML = '<p style="color:#666;padding:10px;">No tracked grants. Click a grant and mark it as Interested.</p>';
    return;
  }
  el.innerHTML = `<table>
    <tr><th>Title</th><th>Agency</th><th>Status</th><th>Interest</th><th>Priority</th><th>Closing</th></tr>
    ${tracked.map(t => {
      const g = t.grant;
      const tr = t.tracking;
      const pLabels = ['Normal', 'High', 'Urgent'];
      const pColors = ['#666', '#ffaa00', '#ff4444'];
      return \`<tr onclick="openGrantDetail('\${g.id}')" style="cursor:pointer">
        <td>\${(g.title || '').substring(0, 50)}</td>
        <td>\${(g.agency || '').substring(0, 25)}</td>
        <td class="\${g.status === 'Open' ? 'status-open' : 'status-closed'}">\${g.status}</td>
        <td><span class="interest-badge interest-\${tr.interest}">\${tr.interest}</span></td>
        <td style="color:\${pColors[tr.priority]}">\${pLabels[tr.priority]}</td>
        <td>\${g.closing_date || ''}</td>
      </tr>\`;
    }).join('')}
  </table>`;
}

// ── Scheduler Controls ──────────────────────────────

async function loadSchedulerStatus() {
  try {
    const s = await fetchJSON('/api/scheduler');
    const el = document.getElementById('sched-status');
    if (s.status === 'running') {
      const nextRun = s.jobs.length > 0 ? s.jobs[0].next_run : '';
      el.innerHTML = '<span style="color:#00ff88">Running</span> — Next: ' + (nextRun || 'N/A');
    } else {
      el.innerHTML = '<span style="color:#666">Stopped</span>';
    }
  } catch(e) {}
}

async function toggleScheduler(enable) {
  const hour = parseInt(document.getElementById('sched-hour').value) || 6;
  const minute = parseInt(document.getElementById('sched-minute').value) || 0;
  try {
    const resp = await fetch(API + '/api/scheduler', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ enabled: enable, cron_hour: hour, cron_minute: minute })
    });
    const r = await resp.json();
    showToast(enable ? 'Scheduler started at ' + r.schedule : 'Scheduler stopped');
    loadSchedulerStatus();
  } catch(e) { showToast('Error: ' + e.message); }
}

// ── Email Config ────────────────────────────────────

async function loadEmailConfig() {
  try {
    const cfg = await fetchJSON('/api/notify/config');
    document.getElementById('smtp-host').value = cfg.smtp_host || '';
    document.getElementById('smtp-port').value = cfg.smtp_port || 587;
    document.getElementById('smtp-user').value = cfg.smtp_user || '';
    document.getElementById('smtp-to').value = cfg.notify_to || '';
  } catch(e) {}
}

async function saveEmailConfig() {
  try {
    const resp = await fetch(API + '/api/notify/config', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        smtp_host: document.getElementById('smtp-host').value,
        smtp_port: parseInt(document.getElementById('smtp-port').value) || 587,
        smtp_user: document.getElementById('smtp-user').value,
        smtp_password: document.getElementById('smtp-pass').value,
        notify_to: document.getElementById('smtp-to').value,
      })
    });
    showToast('Email config saved');
  } catch(e) { showToast('Error: ' + e.message); }
}

async function sendTestEmail() {
  try {
    const resp = await fetch(API + '/api/notify/test', { method: 'POST' });
    if (resp.ok) showToast('Test email sent!');
    else { const e = await resp.json(); showToast('Failed: ' + (e.detail || 'Error')); }
  } catch(e) { showToast('Error: ' + e.message); }
}

// ── Provider Comparison ─────────────────────────────

async function compareProviders() {
  if (!currentGrantId) return;

  const orgName = document.getElementById('propose-org').value.trim();
  const focusArea = document.getElementById('propose-focus').value.trim();
  const btn = event.target;

  btn.disabled = true;
  btn.textContent = 'Comparing...';
  document.getElementById('compare-result').style.display = 'none';
  document.getElementById('proposal-result').style.display = 'none';

  try {
    const resp = await fetch(API + '/api/grants/' + currentGrantId + '/compare', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        org_name: orgName || null,
        focus_area: focusArea || null,
        providers: ['deepseek', 'anthropic'],
        refine: false
      })
    });

    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.detail || 'Comparison failed');
    }

    const results = await resp.json();
    const grid = document.getElementById('compare-grid');
    let html = '';

    for (const r of results) {
      const proposal = await fetchJSON('/api/proposals/' + r.proposal_id);
      const content = proposal.content_en || 'No content';
      html += \`
        <div class="compare-panel">
          <h4>\${r.provider.toUpperCase()} — \${r.model}</h4>
          <div class="compare-meta">
            <span>\${r.words.toLocaleString()} words</span>
            <span>\${r.tokens_used.toLocaleString()} tokens</span>
          </div>
          <div class="content-preview">\${content}</div>
          <div style="margin-top:8px;display:flex;gap:6px">
            <button class="crawl-btn" onclick="window.open('/api/proposals/\${r.proposal_id}/export?format=docx')" style="font-size:11px;padding:4px 10px;background:#1a1a1a;color:#00ff88;border:1px solid #00ff88">DOCX</button>
            <button class="crawl-btn" onclick="window.open('/api/proposals/\${r.proposal_id}/export?format=pdf')" style="font-size:11px;padding:4px 10px;background:#1a1a1a;color:#00ff88;border:1px solid #00ff88">PDF</button>
          </div>
        </div>\`;
    }

    grid.innerHTML = html;
    document.getElementById('compare-result').style.display = 'block';
    loadProposals();
    showToast('Comparison complete! ' + results.length + ' providers');

  } catch(e) {
    showToast('Error: ' + e.message);
  }

  btn.disabled = false;
  btn.textContent = 'Compare Providers';
}

// Close modal with Escape key
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeModal(); });

// Init
loadStats();
loadAnalytics();
loadGrants();
loadTrackedGrants();
loadProposals();
loadCrawlHistory();
loadSchedulerStatus();
loadEmailConfig();
</script>
</body>
</html>"""
