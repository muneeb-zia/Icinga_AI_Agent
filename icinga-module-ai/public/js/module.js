

// =============================================================================
// ICINGA AI AGENT — NATIVE WEB 2 INTEGRATION (V2.5 ENTERPRISE UPGRADE)
// Live Groq Cloud LPU (GPT-OSS 20B+) • 47 Tools • Hybrid RAG • DevOps NOC Suite
// Real-time SSE Streaming • Markdown Tables • HITL Safety • Maximizable Panel
// =============================================================================

(function() {
    'use strict';

    var API_BASE = 'http://localhost:8000';
    var TOOLS_COUNT = 48;
    var SESSION_ID = 'icinga-web-' + Math.random().toString(36).substring(2, 9);
    var ACTIVE_TAB = 'rag'; // 'rag', 'devops', 'actions'
    var IS_MAXIMIZED = false;

    var STYLES = [
        '#ai-agent-widget { position: fixed; bottom: 24px; right: 24px; z-index: 99999; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; display: flex; flex-direction: column; align-items: flex-end; }',
        '#ai-widget-btn { background: linear-gradient(135deg, #0284c7 0%, #0369a1 50%, #0f172a 100%); color: #ffffff; border: none; border-radius: 50%; width: 62px; height: 62px; font-size: 30px; cursor: pointer; box-shadow: 0 8px 26px rgba(2, 132, 199, 0.45); display: flex; justify-content: center; align-items: center; transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275); position: relative; }',
        '#ai-widget-btn:hover { transform: scale(1.08) translateY(-3px); box-shadow: 0 12px 32px rgba(2, 132, 199, 0.6); }',
        '#ai-widget-badge { position: absolute; top: -3px; right: -3px; background: #10b981; color: #ffffff; font-size: 0.62rem; font-weight: 800; padding: 2px 6px; border-radius: 10px; border: 2px solid #ffffff; box-shadow: 0 2px 8px rgba(16, 185, 129, 0.6); letter-spacing: 0.5px; }',
        '#ai-widget-panel { background: #ffffff; width: 480px; height: 650px; max-height: calc(100vh - 110px); border-radius: 18px; box-shadow: 0 24px 60px rgba(15, 23, 42, 0.28), 0 0 0 1px rgba(226, 232, 240, 0.8); display: none; flex-direction: column; overflow: hidden; margin-bottom: 16px; animation: aiSlideUp 0.25s cubic-bezier(0.16, 1, 0.3, 1); transition: width 0.25s ease, height 0.25s ease; }',
        '#ai-widget-panel.ai-open { display: flex; }',
        '#ai-widget-panel.ai-maximized { width: 720px; height: 820px; max-height: calc(100vh - 80px); }',
        '@keyframes aiSlideUp { from { opacity: 0; transform: translateY(20px) scale(0.97); } to { opacity: 1; transform: translateY(0) scale(1); } }',
        
        // Header
        '.ai-hdr { background: linear-gradient(135deg, #0b1329 0%, #1e293b 60%, #0369a1 100%); color: #ffffff; padding: 14px 18px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.12); position: relative; }',
        '.ai-hdr-left { display: flex; align-items: center; gap: 12px; }',
        '.ai-hdr-icon { font-size: 1.6rem; filter: drop-shadow(0 2px 4px rgba(0,0,0,0.3)); }',
        '.ai-hdr-title { font-size: 1.02rem; font-weight: 700; margin: 0; color: #ffffff; letter-spacing: -0.2px; display: flex; align-items: center; gap: 8px; }',
        '.ai-hdr-pill { background: rgba(2, 132, 199, 0.3); border: 1px solid #38bdf8; color: #38bdf8; font-size: 0.65rem; padding: 1px 7px; border-radius: 12px; font-weight: 600; text-transform: uppercase; }',
        '.ai-hdr-sub { font-size: 0.72rem; color: #94a3b8; display: flex; align-items: center; gap: 6px; margin-top: 2px; }',
        '.ai-hdr-dot { width: 7px; height: 7px; background: #10b981; border-radius: 50%; box-shadow: 0 0 8px #10b981; display: inline-block; animation: aiPulseDot 2s infinite; }',
        '@keyframes aiPulseDot { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.5; transform: scale(0.85); } }',
        '.ai-hdr-actions { display: flex; gap: 6px; }',
        '.ai-hdr-btn { background: rgba(255,255,255,0.12); border: none; color: #ffffff; border-radius: 7px; width: 30px; height: 30px; cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 0.85rem; transition: all 0.15s ease; }',
        '.ai-hdr-btn:hover { background: rgba(255,255,255,0.25); transform: translateY(-1px); }',
        
        // Company GPU Model Switcher Bar
        '.ai-model-bar { background: #090f1d; border-bottom: 1px solid rgba(255,255,255,0.08); padding: 7px 14px; display: flex; justify-content: space-between; align-items: center; }',
        '.ai-model-bar-left { display: flex; align-items: center; gap: 8px; }',
        '.ai-gpu-dot { width: 8px; height: 8px; background: #10b981; border-radius: 50%; box-shadow: 0 0 8px #10b981; display: inline-block; animation: aiPulseDot 2s infinite; }',
        '.ai-gpu-dot.ai-offline { background: #ef4444; box-shadow: 0 0 8px #ef4444; }',
        '.ai-gpu-title { font-size: 0.72rem; font-weight: 700; color: #cbd5e1; display: flex; align-items: center; gap: 5px; }',
        '.ai-model-bar-right { display: flex; align-items: center; gap: 8px; }',
        '.ai-model-select { background: #1e293b; color: #38bdf8; border: 1px solid #334155; border-radius: 6px; padding: 4px 8px; font-size: 0.72rem; font-weight: 600; outline: none; cursor: pointer; transition: all 0.2s ease; max-width: 220px; }',
        '.ai-model-select:hover, .ai-model-select:focus { border-color: #38bdf8; box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.25); }',
        '.ai-gpu-vram-badge { background: rgba(16, 185, 129, 0.15); border: 1px solid #10b981; color: #34d399; font-size: 0.64rem; font-weight: 700; padding: 2px 6px; border-radius: 4px; letter-spacing: 0.3px; }',
        '.ai-sys-notice { align-self: center; background: #f0fdf4; border: 1px solid #bbf7d0; color: #166534; padding: 6px 12px; border-radius: 8px; font-size: 0.74rem; font-weight: 600; margin: 4px 0; text-align: center; width: 90%; animation: aiSlideUp 0.2s ease; }',
        
        // Context Bar
        '.ai-context-bar { background: #f0f7ff; border-bottom: 1px solid #e0e7ff; padding: 7px 16px; font-size: 0.74rem; color: #1e3a8a; display: flex; justify-content: space-between; align-items: center; font-weight: 500; }',
        '.ai-ctx-badge { background: #dbeafe; color: #1d4ed8; padding: 2px 8px; border-radius: 6px; font-weight: 600; font-family: monospace; }',
        '.ai-ctx-quick-btn { background: #0284c7; color: #ffffff; border: none; border-radius: 4px; padding: 3px 8px; font-size: 0.7rem; cursor: pointer; font-weight: 600; transition: background 0.15s; }',
        '.ai-ctx-quick-btn:hover { background: #0369a1; }',

        // Tabs Bar
        '.ai-tabs { display: flex; background: #f8fafc; border-bottom: 1px solid #e2e8f0; padding: 6px 12px; gap: 6px; }',
        '.ai-tab-btn { flex: 1; border: 1px solid #e2e8f0; background: #ffffff; color: #64748b; padding: 6px 8px; border-radius: 8px; font-size: 0.74rem; font-weight: 600; cursor: pointer; text-align: center; transition: all 0.15s ease; display: flex; align-items: center; justify-content: center; gap: 4px; }',
        '.ai-tab-btn:hover { background: #f1f5f9; color: #0f172a; }',
        '.ai-tab-btn.ai-tab-active { background: #0284c7; color: #ffffff; border-color: #0284c7; box-shadow: 0 2px 6px rgba(2, 132, 199, 0.3); }',

        // Body & History
        '.ai-body { flex: 1; display: flex; flex-direction: column; background: #f8fafc; overflow: hidden; }',
        '.ai-history { flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 14px; scroll-behavior: smooth; }',
        '.ai-msg { padding: 12px 16px; border-radius: 14px; max-width: 90%; font-size: 0.865rem; line-height: 1.55; word-wrap: break-word; }',
        '.ai-u { background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%); color: #ffffff; align-self: flex-end; border-bottom-right-radius: 4px; box-shadow: 0 3px 12px rgba(2, 132, 199, 0.28); }',
        '.ai-b { background: #ffffff; color: #1e293b; align-self: flex-start; border-bottom-left-radius: 4px; border: 1px solid #e2e8f0; box-shadow: 0 2px 8px rgba(0,0,0,0.04); }',
        
        // Tool Badge
        '.ai-tool-badge { display: inline-flex; align-items: center; gap: 7px; background: #f0f9ff; color: #0369a1; border: 1px solid #bae6fd; padding: 5px 12px; border-radius: 16px; font-size: 0.74rem; font-weight: 600; margin-bottom: 10px; animation: aiPulse 1.6s infinite; }',
        '@keyframes aiPulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.6; } }',
        
        // Quick Chips Area
        '.ai-chips { display: flex; flex-direction: column; gap: 6px; margin-top: 10px; }',
        '.ai-chip-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }',
        '.ai-chip { background: #ffffff; border: 1px solid #cbd5e1; color: #334155; padding: 8px 10px; border-radius: 8px; font-size: 0.75rem; font-weight: 500; cursor: pointer; transition: all 0.15s ease; text-align: left; display: flex; align-items: center; gap: 6px; }',
        '.ai-chip:hover { background: #f0f9ff; color: #0284c7; border-color: #38bdf8; transform: translateY(-1px); box-shadow: 0 2px 8px rgba(2, 132, 199, 0.15); }',
        '.ai-chip strong { color: #0f172a; }',

        // Human-in-the-loop Approval Box
        '.ai-hitl-box { margin-top: 12px; padding: 12px 14px; background: #fffbeb; border: 1px solid #fef3c7; border-radius: 10px; display: flex; flex-direction: column; gap: 8px; box-shadow: 0 2px 6px rgba(217, 119, 6, 0.1); }',
        '.ai-hitl-title { font-size: 0.78rem; font-weight: 700; color: #92400e; display: flex; align-items: center; gap: 6px; }',
        '.ai-hitl-btns { display: flex; gap: 10px; margin-top: 4px; }',
        '.ai-btn-confirm { background: #16a34a; color: #ffffff; border: none; padding: 7px 16px; border-radius: 7px; font-size: 0.78rem; cursor: pointer; font-weight: 600; transition: background 0.15s; }',
        '.ai-btn-confirm:hover { background: #15803d; }',
        '.ai-btn-cancel { background: #dc2626; color: #ffffff; border: none; padding: 7px 16px; border-radius: 7px; font-size: 0.78rem; cursor: pointer; font-weight: 600; transition: background 0.15s; }',
        '.ai-btn-cancel:hover { background: #b91c1c; }',

        // Input Row
        '.ai-row { padding: 12px 16px; background: #ffffff; border-top: 1px solid #e2e8f0; display: flex; gap: 10px; align-items: center; }',
        '.ai-row input { flex: 1; padding: 11px 16px; border: 1px solid #cbd5e1; border-radius: 24px; outline: none; font-size: 0.865rem; transition: all 0.15s; color: #1e293b; }',
        '.ai-row input:focus { border-color: #0284c7; box-shadow: 0 0 0 3px rgba(2, 132, 199, 0.18); }',
        '.ai-row button { background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%); color: #ffffff; border: none; border-radius: 50%; width: 42px; height: 42px; cursor: pointer; font-size: 18px; display: flex; justify-content: center; align-items: center; transition: all 0.15s; box-shadow: 0 2px 8px rgba(2, 132, 199, 0.35); flex-shrink: 0; }',
        '.ai-row button:hover { transform: scale(1.05); background: #0369a1; }',

        // Markdown Elements & Tables
        '.ai-msg pre { background: #0f172a; color: #f8fafc; padding: 10px 12px; border-radius: 8px; overflow-x: auto; font-size: 0.78rem; margin: 8px 0; border: 1px solid #334155; }',
        '.ai-msg code { font-family: "Consolas", "Courier New", monospace; }',
        '.ai-inline-code { background: #f1f5f9; color: #0369a1; padding: 2px 6px; border-radius: 4px; font-size: 0.8rem; border: 1px solid #e2e8f0; }',
        '.ai-code-block { margin: 8px 0; border-radius: 8px; overflow: hidden; border: 1px solid #334155; }',
        '.ai-code-hdr { background: #1e293b; color: #94a3b8; font-size: 0.7rem; font-weight: 600; padding: 5px 12px; display: flex; justify-content: space-between; align-items: center; text-transform: uppercase; }',
        '.ai-copy-btn { background: rgba(255,255,255,0.15); border: none; color: #ffffff; padding: 2px 8px; border-radius: 4px; font-size: 0.68rem; cursor: pointer; font-weight: 600; transition: background 0.15s; }',
        '.ai-copy-btn:hover { background: rgba(255,255,255,0.3); }',
        '.ai-table-wrap { overflow-x: auto; margin: 10px 0; border-radius: 8px; border: 1px solid #e2e8f0; }',
        'table.ai-table { width: 100%; border-collapse: collapse; font-size: 0.76rem; text-align: left; }',
        'table.ai-table th { background: #0f172a; color: #ffffff; padding: 8px 10px; font-weight: 600; }',
        'table.ai-table td { padding: 6px 10px; border-bottom: 1px solid #e2e8f0; }',
        'table.ai-table tr:nth-child(even) { background: #f8fafc; }',
        'table.ai-table tr:hover { background: #f1f5f9; }',
        '.ai-h2 { margin: 12px 0 6px; font-size: 1.05rem; font-weight: 700; color: #0f172a; }',
        '.ai-h3 { margin: 10px 0 4px; font-size: 0.95rem; font-weight: 700; color: #0369a1; }',
        '.ai-h4 { margin: 8px 0 4px; font-size: 0.88rem; font-weight: 600; color: #1e293b; }',
        '.ai-blockquote { border-left: 3px solid #0284c7; background: #f0f9ff; padding: 6px 12px; margin: 8px 0; border-radius: 0 6px 6px 0; color: #0369a1; font-size: 0.82rem; }',
        '.ai-ul { margin: 6px 0; padding-left: 18px; }',
        '.ai-ul li { margin-bottom: 3px; }',
        '.ai-cursor { display: inline-block; width: 6px; height: 14px; background: #0284c7; margin-left: 2px; vertical-align: middle; animation: aiBlink 0.8s infinite; }',
        '@keyframes aiBlink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }'
    ].join('');

    // Robust Markdown Converter
    function renderMarkdown(text) {
        if (!text) return '';
        var out = text;
        
        // Escape basic HTML
        out = out.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

        // Fenced Code blocks ```lang ... ```
        out = out.replace(/```([a-z0-9_\-]*)\n([\s\S]*?)```/gi, function(match, lang, code) {
            var raw = code.replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>');
            return '<div class="ai-code-block"><div class="ai-code-hdr"><span>' + (lang || 'terminal') + '</span><button class="ai-copy-btn" onclick="navigator.clipboard.writeText(decodeURIComponent(\'' + encodeURIComponent(raw) + '\'));this.textContent=\'Copied!\';var b=this;setTimeout(function(){b.textContent=\'Copy\';},1500);">Copy</button></div><pre><code>' + code.trim() + '</code></pre></div>';
        });

        // Inline code `...`
        out = out.replace(/`([^`]+)`/g, '<code class="ai-inline-code">$1</code>');

        // Bold: **text**
        out = out.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

        // Italic: *text*
        out = out.replace(/\*([^*]+)\*/g, '<em>$1</em>');

        // Markdown Tables
        out = out.replace(/((?:^|\n)\|[^\n]+\|\r?\n\|[\s\-:|]+\|\r?\n(?:\|[^\n]+\|\r?\n?)+)/g, function(tableStr) {
            var rows = tableStr.trim().split('\n');
            if (rows.length < 2) return tableStr;
            var html = '<div class="ai-table-wrap"><table class="ai-table">';
            var headerCols = rows[0].split('|').slice(1, -1);
            html += '<thead><tr>';
            for (var h = 0; h < headerCols.length; h++) {
                html += '<th>' + headerCols[h].trim() + '</th>';
            }
            html += '</tr></thead><tbody>';
            for (var r = 2; r < rows.length; r++) {
                var cols = rows[r].split('|').slice(1, -1);
                if (cols.length === 0) continue;
                html += '<tr>';
                for (var c = 0; c < cols.length; c++) {
                    html += '<td>' + cols[c].trim() + '</td>';
                }
                html += '</tr>';
            }
            html += '</tbody></table></div>';
            return html;
        });

        // Headers
        out = out.replace(/^### (.*$)/gim, '<h4 class="ai-h4">$1</h4>');
        out = out.replace(/^## (.*$)/gim, '<h3 class="ai-h3">$1</h3>');
        out = out.replace(/^# (.*$)/gim, '<h2 class="ai-h2">$1</h2>');

        // Blockquotes
        out = out.replace(/^\> (.*$)/gim, '<blockquote class="ai-blockquote">$1</blockquote>');

        // Lists
        out = out.replace(/^\s*[-•*]\s+(.*)$/gim, '<li>$1</li>');
        out = out.replace(/((?:<li>.*<\/li>\s*)+)/gims, '<ul class="ai-ul">$1</ul>');

        // Line breaks
        out = out.replace(/\n\n/g, '<br><br>').replace(/\n/g, '<br>');

        return out;
    }

    function getUserRoleBadge(username) {
        var roleStr = ' (Tier 4: Admin)';
        var bg = '#fef3c7';
        var color = '#92400e';
        if (username === 'junior_operator') {
            roleStr = ' (Tier 1: L1 Read-Only)';
            bg = '#e0f2fe';
            color = '#0369a1';
        } else if (username === 'senior_sre') {
            roleStr = ' (Tier 2: L2 NOC Senior)';
            bg = '#dcfce7';
            color = '#15803d';
        }
        return '<span class="ai-ctx-badge" style="background:' + bg + ';color:' + color + ';margin-left:6px;font-size:0.68rem;font-weight:600;" title="Authenticated Icinga Web 2 User">👤 ' + (username || 'admin') + roleStr + '</span>';
    }

    function getIcingaContext() {
        var params = new URLSearchParams(window.location.search);
        var host = params.get('host') || '';
        var service = params.get('service') || '';

        if (!host) {
            var hostElem = document.querySelector('.host-header, [data-icinga-host], .icinga-detail-header h1');
            if (hostElem && hostElem.textContent) {
                host = hostElem.textContent.trim().split(' ')[0];
            }
        }

        // Authenticated Icinga Web 2 User Detection
        var username = 'admin';
        var userLink = document.querySelector('.user-nav-item a, a[href*="account"], #user-menu, .user-name');
        if (userLink) {
            var clone = userLink.cloneNode(true);
            var ball = clone.querySelector('.user-ball');
            if (ball) ball.remove();
            var txt = clone.textContent.trim().replace(/^👤\s*/, '');
            if (txt) username = txt;
        }

        return { host: host, service: service, username: username };
    }

    var CHIP_SETS = {
        rag: [
            { label: '💡 Disk Space RCA', q: 'The disk service on icinga-master is critical. How do I fix it?' },
            { label: '🔍 MySQL High CPU', q: 'MySQL CPU usage is at 98%. Search runbooks for triage steps.' },
            { label: '📜 Search Logs (24h)', q: 'Search OpenSearch logs for errors or timeouts in the last 24h.' },
            { label: '🔒 SSL Expiry Runbook', q: 'How do I troubleshoot SSL certificate expiry alerts in Icinga?' }
        ],
        devops: [
            { label: '🌲 Auto-Generate BPM Tree', q: 'Auto-generate a BPM Business Process service tree for E-Commerce Payment Gateway with quorum evaluation.' },
            { label: '📊 30-Day SLA Report', q: 'Generate a 30-day SLA and Incident Health Report for RetailCorp Global.' },
            { label: '🎯 Smart Context Router', q: 'Route a smart notification for host api-auth-01 service check_http in CRITICAL state with error: HTTP 500 NullPointerException at AuthFilter.java:88' },
            { label: '📋 24/7 NOC Shift Handover', q: 'Compile and generate the 24/7 NOC shift handover briefing for Shift Alpha to Shift Beta.' },
            { label: '🛡️ Check RBAC Security', q: 'Check if an L1 user can execute acknowledge_alert, and verify if an L2 user can.' }
        ],
        actions: [
            { label: '📌 Acknowledge Problem', q: 'Acknowledge the problem on icinga-master' },
            { label: '⏱️ Schedule Downtime', q: 'Schedule 2 hours downtime for icinga-master for OS patching' },
            { label: '💬 Add Host Comment', q: 'Add a comment to icinga-master: Verified AI agent automation' },
            { label: '🔄 Force Re-check', q: 'Force a re-check on icinga-master' }
        ]
    };

    function renderChips(container, category) {
        container.innerHTML = '';
        var list = CHIP_SETS[category] || CHIP_SETS.rag;
        var grid = document.createElement('div');
        grid.className = 'ai-chip-grid';
        
        list.forEach(function(item) {
            var chip = document.createElement('div');
            chip.className = 'ai-chip';
            chip.setAttribute('data-q', item.q);
            chip.innerHTML = item.label;
            grid.appendChild(chip);
        });
        container.appendChild(grid);
    }

    function boot() {
        if (document.getElementById('ai-agent-widget')) return;

        var s = document.createElement('style');
        s.textContent = STYLES;
        document.head.appendChild(s);

        var wrap = document.createElement('div');
        wrap.id = 'ai-agent-widget';

        var panel = document.createElement('div');
        panel.id = 'ai-widget-panel';

        // Header
        var hdr = document.createElement('div');
        hdr.className = 'ai-hdr';
        hdr.innerHTML = [
            '<div class="ai-hdr-left">',
            '  <span class="ai-hdr-icon">🤖</span>',
            '  <div>',
            '    <h3 class="ai-hdr-title">Icinga AIOps Copilot <span class="ai-hdr-pill">2.5 Enterprise</span></h3>',
            '    <div class="ai-hdr-sub" id="ai-hdr-model-info">',
            '      <span class="ai-hdr-dot"></span>',
            '      <span>🏢 Company GPU (gpt-oss:20b) &bull; 47 Tools Active &bull; Sentry APM</span>',
            '    </div>',
            '  </div>',
            '</div>',
            '<div class="ai-hdr-actions">',
            '  <button class="ai-hdr-btn" id="ai-max-btn" title="Maximize/Restore">⛶</button>',
            '  <button class="ai-hdr-btn" id="ai-clear-btn" title="Reset Session">🔄</button>',
            '  <button class="ai-hdr-btn" id="ai-cls-btn" title="Close Panel">&times;</button>',
            '</div>'
        ].join('');
        panel.appendChild(hdr);

        // Company GPU Model Switcher Bar
        var modelBar = document.createElement('div');
        modelBar.className = 'ai-model-bar';
        modelBar.id = 'ai-model-bar';
        modelBar.innerHTML = [
            '<div class="ai-model-bar-left">',
            '  <span class="ai-gpu-dot" id="ai-gpu-dot"></span>',
            '  <span class="ai-gpu-title" id="ai-gpu-title">🏢 Company GPU</span>',
            '</div>',
            '<div class="ai-model-bar-right">',
            '  <select class="ai-model-select" id="ai-model-select" title="Switch Model on Company GPU">',
            '    <option value="gpt-oss:20b" selected>⚡ gpt-oss:20b (114 tok/s)</option>',
            '    <option value="qwen3:14b">🧠 qwen3:14b (Reasoning)</option>',
            '    <option value="gemma4:12b">🎯 gemma4:12b (Precision)</option>',
            '    <option value="gemma4:e4b">🚀 gemma4:e4b (Fast)</option>',
            '    <option value="llama3.1:8b-instruct-q4_K_M">🦙 llama3.1:8b (Instruct)</option>',
            '    <option value="llama3.1:8b">💻 localhost (llama3.1:8b)</option>',
            '  </select>',
            '  <span class="ai-gpu-vram-badge" id="ai-gpu-vram-badge">16GB VRAM</span>',
            '</div>'
        ].join('');
        panel.appendChild(modelBar);

        // Context Bar
        var ctxBar = document.createElement('div');
        ctxBar.className = 'ai-context-bar';
        ctxBar.id = 'ai-ctx-bar';

        function updateContextBar() {
            var ctx = getIcingaContext();
            var userBadge = getUserRoleBadge(ctx.username);
            if (ctx.host) {
                ctxBar.innerHTML = '<span>📍 Context: <span class="ai-ctx-badge">' + ctx.host + (ctx.service ? ' / ' + ctx.service : '') + '</span>' + userBadge + '</span><div><button class="ai-ctx-quick-btn" id="ai-ctx-diag">Diagnose Live</button></div>';
                var diagBtn = document.getElementById('ai-ctx-diag');
                if (diagBtn) {
                    diagBtn.addEventListener('click', function(e) {
                        e.stopPropagation();
                        sendQuery('Diagnose current status and recent logs for host ' + ctx.host + (ctx.service ? ' service ' + ctx.service : ''));
                    });
                }
            } else {
                ctxBar.innerHTML = '<span>🌐 Infrastructure View ' + userBadge + '</span><span style="color:#0284c7;font-size:0.7rem;font-weight:600;">Real-time RBAC Gated</span>';
            }
        }
        updateContextBar();
        panel.appendChild(ctxBar);

        // Pillar Tabs Bar
        var tabsBar = document.createElement('div');
        tabsBar.className = 'ai-tabs';
        tabsBar.innerHTML = [
            '<button class="ai-tab-btn ai-tab-active" data-tab="rag">🔍 RAG & RCA</button>',
            '<button class="ai-tab-btn" data-tab="devops">🛠️ DevOps Suite</button>',
            '<button class="ai-tab-btn" data-tab="actions">⚡ HITL Actions</button>'
        ].join('');
        panel.appendChild(tabsBar);

        // Body
        var body = document.createElement('div');
        body.className = 'ai-body';
        var hist = document.createElement('div');
        hist.className = 'ai-history';
        hist.id = 'ai-hist';

        // Welcome Message
        var welcomeMsg = document.createElement('div');
        welcomeMsg.className = 'ai-msg ai-b';
        welcomeMsg.innerHTML = [
            '<p style="margin:0 0 6px 0;">👋 <strong>Welcome to Icinga Enterprise AIOps Copilot</strong></p>',
            '<p style="font-size:0.8rem;color:#64748b;margin:0 0 10px 0;">Powered by <strong>local or cloud LLMs</strong>, LangGraph state engine, OpenSearch vector embeddings, and full NOC L1–L4 automation. You can switch between Company GPU models dynamically in the top bar. Select a scenario or ask anything:</p>',
            '<div class="ai-chips" id="ai-quick-chips"></div>'
        ].join('');
        hist.appendChild(welcomeMsg);
        body.appendChild(hist);

        // Input Row
        var row = document.createElement('div');
        row.className = 'ai-row';
        var inp = document.createElement('input');
        inp.type = 'text';
        inp.id = 'ai-inp';
        inp.placeholder = 'Diagnose alert, auto-build BPM DAG, or request SLA report...';
        var snd = document.createElement('button');
        snd.id = 'ai-snd';
        snd.title = 'Send Message';
        snd.innerHTML = '&#10148;';
        row.appendChild(inp);
        row.appendChild(snd);
        body.appendChild(row);
        panel.appendChild(body);

        // Floating Action Launcher Button
        var fab = document.createElement('button');
        fab.id = 'ai-widget-btn';
        fab.innerHTML = '🤖<div id="ai-widget-badge">2.5</div>';

        wrap.appendChild(panel);
        wrap.appendChild(fab);
        document.body.appendChild(wrap);

        // 1. Launcher Button Click - bind immediately & defensively
        fab.addEventListener('click', function(e) {
            e.stopPropagation();
            panel.classList.toggle('ai-open');
            if (panel.classList.contains('ai-open')) {
                updateContextBar();
                if (inp) inp.focus();
            }
        });

        // 2. Close Button
        var clsBtn = document.getElementById('ai-cls-btn') || document.getElementById('ai-btn-close');
        if (clsBtn) {
            clsBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                panel.classList.remove('ai-open');
            });
        }

        // 3. Maximize / Expand Toggle
        var maxBtn = document.getElementById('ai-max-btn') || document.getElementById('ai-btn-max');
        if (maxBtn) {
            maxBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                IS_MAXIMIZED = !IS_MAXIMIZED;
                if (IS_MAXIMIZED) {
                    panel.classList.add('ai-maximized');
                    maxBtn.innerHTML = '🗗';
                    maxBtn.title = 'Restore Window';
                } else {
                    panel.classList.remove('ai-maximized');
                    maxBtn.innerHTML = '⛶';
                    maxBtn.title = 'Expand Window';
                }
            });
        }

        // 4. Clear / Reset Session Button
        var clearBtn = document.getElementById('ai-clear-btn');
        if (clearBtn) {
            clearBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                hist.innerHTML = '';
                hist.appendChild(welcomeMsg);
                var chips = welcomeMsg.querySelector('#ai-quick-chips');
                if (chips) renderChips(chips, ACTIVE_TAB);
                SESSION_ID = 'icinga-web-' + Math.random().toString(36).substring(2, 9);
            });
        }

        // 5. Initial Chip Rendering
        var chipsContainer = welcomeMsg.querySelector('#ai-quick-chips');
        if (chipsContainer) {
            renderChips(chipsContainer, ACTIVE_TAB);
        }

        // 6. Tab Switching Event
        if (tabsBar) {
            tabsBar.addEventListener('click', function(e) {
                var target = e.target.closest('.ai-tab-btn');
                if (!target) return;
                var tab = target.getAttribute('data-tab');
                if (!tab) return;
                
                ACTIVE_TAB = tab;
                tabsBar.querySelectorAll('.ai-tab-btn').forEach(function(btn) {
                    btn.classList.remove('ai-tab-active');
                });
                target.classList.add('ai-tab-active');
                if (chipsContainer) renderChips(chipsContainer, ACTIVE_TAB);
            });
        }

        // Chip and Button Delegation
        panel.addEventListener('click', function(e) {
            var chip = e.target.closest('.ai-chip');
            if (chip) {
                var query = chip.getAttribute('data-q');
                if (query) sendQuery(query);
            }
            if (e.target && e.target.classList.contains('ai-btn-confirm')) {
                sendQuery('Yes, proceed with the action.');
            }
            if (e.target && e.target.classList.contains('ai-btn-cancel')) {
                sendQuery('No, cancel this action.');
            }
        });

        // Company GPU Dynamic Model Switching Logic
        var modelSelect = panel.querySelector('#ai-model-select');
        var gpuDot = panel.querySelector('#ai-gpu-dot');
        var gpuTitle = panel.querySelector('#ai-gpu-title');
        var hdrSub = panel.querySelector('#ai-hdr-model-info');

        function loadAvailableModels() {
            fetch(API_BASE + '/api/models')
                .then(function(res) { return res.json(); })
                .then(function(data) {
                    if (data.models && data.models.length > 0) {
                        modelSelect.innerHTML = '';
                        data.models.forEach(function(m) {
                            var opt = document.createElement('option');
                            opt.value = m.id;
                            opt.dataset.provider = m.provider || 'ollama';
                            opt.textContent = m.badge + ' ' + m.name;
                            if (m.id === data.active_model) {
                                opt.selected = true;
                            }
                            modelSelect.appendChild(opt);
                        });
                    }
                    TOOLS_COUNT = data.tools_count || TOOLS_COUNT;
                    var vramBadge = panel.querySelector('#ai-gpu-vram-badge');
                    if (data.active_provider === 'groq') {
                        gpuDot.className = 'ai-gpu-dot';
                        gpuTitle.innerHTML = '⚡ Groq Cloud LPU (Connected)';
                        if (vramBadge) vramBadge.textContent = 'Cloud';
                    } else if (data.gpu_connected) {
                        gpuDot.className = 'ai-gpu-dot';
                        gpuTitle.innerHTML = '🏢 GPU Server (Connected)';
                    } else {
                        gpuDot.className = 'ai-gpu-dot ai-offline';
                        gpuTitle.innerHTML = '🏢 GPU Server (Offline)';
                    }
                    if (hdrSub) {
                        hdrSub.innerHTML = '<span class="ai-hdr-dot"></span><span>' + (data.active_server_label || 'GPU Server') + ' (' + data.active_model + ') &bull; ' + TOOLS_COUNT + ' Tools</span>';
                    }
                })
                .catch(function(err) {
                    console.warn('Could not load models from API:', err);
                });
        }
        loadAvailableModels();

        if (modelSelect) {
            modelSelect.addEventListener('change', function() {
                var chosenModel = modelSelect.value;
                var chosenProvider = modelSelect.selectedOptions[0].dataset.provider || 'ollama';
                modelSelect.disabled = true;
                modelSelect.style.opacity = '0.6';

                fetch(API_BASE + '/api/model', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ model: chosenModel, provider: chosenProvider })
                })
                .then(function(res) { return res.json(); })
                .then(function(data) {
                    modelSelect.disabled = false;
                    modelSelect.style.opacity = '1';
                    if (hdrSub) {
                        hdrSub.innerHTML = '<span class="ai-hdr-dot"></span><span>' + (data.server_label || 'GPU Server') + ' (' + chosenModel + ') &bull; ' + TOOLS_COUNT + ' Tools</span>';
                    }
                    var notice = document.createElement('div');
                    notice.className = 'ai-sys-notice';
                    notice.innerHTML = '⚡ <strong>LLM Switched:</strong> Active model is now <code>' + chosenModel + '</code> on ' + (data.server_label || 'Company GPU');
                    hist.appendChild(notice);
                    hist.scrollTop = hist.scrollHeight;
                })
                .catch(function(err) {
                    modelSelect.disabled = false;
                    modelSelect.style.opacity = '1';
                    alert('Failed to switch model: ' + err.message);
                });
            });
        }

        function sendQuery(qText) {
            var q = (qText || inp.value).trim();
            if (!q) return;

            var activeCtx = getIcingaContext();

            // Append User Message
            var uMsg = document.createElement('div');
            uMsg.className = 'ai-msg ai-u';
            uMsg.textContent = q;
            hist.appendChild(uMsg);
            inp.value = '';

            // AI Loading / Stream Message
            var botMsg = document.createElement('div');
            botMsg.className = 'ai-msg ai-b';
            
            var toolBadge = document.createElement('div');
            toolBadge.className = 'ai-tool-badge';
            toolBadge.innerHTML = '⚡ Company GPU Processing...';
            botMsg.appendChild(toolBadge);

            var contentDiv = document.createElement('div');
            contentDiv.className = 'ai-content';
            contentDiv.innerHTML = '<span class="ai-cursor"></span>';
            botMsg.appendChild(contentDiv);

            hist.appendChild(botMsg);
            hist.scrollTop = hist.scrollHeight;

            var accumulatedResponse = '';

            // SSE Streaming
            fetch(API_BASE + '/api/stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query: q,
                    context: activeCtx,
                    username: activeCtx.username,
                    session_id: SESSION_ID
                })
            }).then(function(response) {
                if (!response.ok || !response.body) {
                    throw new Error('Stream request failed');
                }
                var reader = response.body.getReader();
                var decoder = new TextDecoder('utf-8');
                var buffer = '';

                function readStream() {
                    return reader.read().then(function(result) {
                        if (result.done) {
                            finalizeResponse(accumulatedResponse);
                            return;
                        }
                        buffer += decoder.decode(result.value, { stream: true });
                        var lines = buffer.split('\n\n');
                        buffer = lines.pop();

                        for (var i = 0; i < lines.length; i++) {
                            var line = lines[i].trim();
                            if (!line) continue;

                            if (line.indexOf('event: tool_start') !== -1) {
                                var dataStr = line.split('data: ')[1];
                                if (dataStr) {
                                    try {
                                        var d = JSON.parse(dataStr);
                                        toolBadge.style.display = 'inline-flex';
                                        toolBadge.innerHTML = d.message || ('Executing ' + d.tool + '...');
                                    } catch(e){}
                                }
                            } else if (line.indexOf('event: token') !== -1) {
                                var dataStr = line.split('data: ')[1];
                                if (dataStr) {
                                    try {
                                        var d = JSON.parse(dataStr);
                                        accumulatedResponse += d.token;
                                        contentDiv.innerHTML = renderMarkdown(accumulatedResponse) + '<span class="ai-cursor"></span>';
                                        hist.scrollTop = hist.scrollHeight;
                                    } catch(e){}
                                }
                            } else if (line.indexOf('event: done') !== -1) {
                                toolBadge.style.display = 'none';
                            }
                        }
                        return readStream();
                    });
                }
                return readStream();
            }).catch(function() {
                // Fallback to synchronous endpoint
                fetch(API_BASE + '/api/analyze', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        query: q,
                        context: activeCtx,
                        username: activeCtx.username,
                        session_id: SESSION_ID
                    })
                }).then(function(r) { return r.json(); })
                .then(function(data) {
                    toolBadge.style.display = 'none';
                    finalizeResponse(data.response || 'No response returned.');
                }).catch(function() {
                    toolBadge.style.display = 'none';
                    contentDiv.innerHTML = '<span style="color:#dc2626;font-weight:600;">❌ Could not connect to AI Agent API at ' + API_BASE + '. Please verify the backend container is running.</span>';
                });
            });

            function finalizeResponse(fullText) {
                toolBadge.style.display = 'none';
                contentDiv.innerHTML = renderMarkdown(fullText);

                // Detect Human-In-The-Loop Approval Box
                var tail = fullText.toLowerCase().replace(/[’']/g, "'").slice(-400);
                var asksApproval = /shall i (proceed|execute|go ahead)|should i (proceed|go ahead)|(would|do) you (like|want) me to (proceed|go ahead|execute|apply|acknowledge|schedule|restart|create|delete|deploy|add)|please confirm|confirm (that you want|to proceed|the action)/.test(tail);
                if (asksApproval) {
                    var hitlBox = document.createElement('div');
                    hitlBox.className = 'ai-hitl-box';
                    hitlBox.innerHTML = [
                        '<div class="ai-hitl-title">⚠️ Action Requires Operator Confirmation</div>',
                        '<div style="font-size:0.75rem;color:#78350f;">The AI Agent has staged the parameters above. Approve to execute live on Icinga Core.</div>',
                        '<div class="ai-hitl-btns">',
                        '  <button class="ai-btn-confirm">✅ Approve & Execute</button>',
                        '  <button class="ai-btn-cancel">❌ Cancel</button>',
                        '</div>'
                    ].join('');
                    botMsg.appendChild(hitlBox);
                }

                hist.scrollTop = hist.scrollHeight;
            }
        }

        snd.addEventListener('click', function() { sendQuery(); });
        inp.addEventListener('keypress', function(e) { if (e.key === 'Enter') sendQuery(); });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot);
    } else {
        boot();
    }
})();
