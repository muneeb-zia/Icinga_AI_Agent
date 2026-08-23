// SPDX-FileCopyrightText: 2023 Icinga GmbH <https://icinga.com>
// SPDX-License-Identifier: GPL-3.0-or-later

;(function () {
    let html = document.documentElement;
    window.name = html.dataset.icingaWindowName;
    window.icinga = new Icinga({
        baseUrl: html.dataset.icingaBaseUrl,
        locale: html.lang,
        timezone: html.dataset.icingaTimezone
    });

    if (! ('icingaIsIframe' in document.documentElement.dataset)) {
        html.classList.replace('no-js', 'js');
    }

    if (window.getComputedStyle) {
        let matched;
        let element = document.getElementById('layout');
        let name = window
            .getComputedStyle(html)['font-family']
            .replace(/['",]/g, '');

        if (null !== (matched = name.match(/^([a-z]+)-layout$/))) {
            element.classList.replace('default-layout', name);
            if ('object' === typeof window.console) {
                window.console.log('Icinga Web 2: setting initial layout to ' + name);
            }
        }
    }
})();

// =============================================================================
// ICINGA AI AGENT — NATIVE WEB 2 INTEGRATION (V2.0 ENTERPRISE UPGRADE)
// Real-time SSE Streaming, Hybrid RAG, Tool Event Badges, Markdown & HITL Actions
// =============================================================================

(function() {
    'use strict';

    var API_BASE = 'http://localhost:8000';
    var SESSION_ID = 'icinga-web-' + Math.random().toString(36).substring(2, 9);

    var STYLES = [
        '#ai-agent-widget { position: fixed; bottom: 24px; right: 24px; z-index: 99999; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; display: flex; flex-direction: column; align-items: flex-end; }',
        '#ai-widget-btn { background: linear-gradient(135deg, #0088cc 0%, #005580 100%); color: #ffffff; border: none; border-radius: 50%; width: 58px; height: 58px; font-size: 28px; cursor: pointer; box-shadow: 0 6px 20px rgba(0,136,204,0.4); display: flex; justify-content: center; align-items: center; transition: all 0.25s cubic-bezier(0.175, 0.885, 0.32, 1.275); }',
        '#ai-widget-btn:hover { transform: scale(1.08) translateY(-2px); box-shadow: 0 8px 25px rgba(0,136,204,0.55); }',
        '#ai-widget-badge { position: absolute; top: -2px; right: -2px; width: 14px; height: 14px; background: #28a745; border: 2px solid #ffffff; border-radius: 50%; box-shadow: 0 0 8px #28a745; }',
        '#ai-widget-panel { background: #ffffff; width: 420px; height: 580px; border-radius: 16px; box-shadow: 0 12px 40px rgba(0,0,0,0.22); display: none; flex-direction: column; overflow: hidden; margin-bottom: 16px; border: 1px solid #e1e4e8; animation: aiSlideUp 0.25s ease-out; }',
        '#ai-widget-panel.ai-open { display: flex; }',
        '@keyframes aiSlideUp { from { opacity: 0; transform: translateY(16px); } to { opacity: 1; transform: translateY(0); } }',
        '.ai-hdr { background: linear-gradient(135deg, #0f2b48 0%, #0088cc 100%); color: #ffffff; padding: 14px 18px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.1); }',
        '.ai-hdr-left { display: flex; align-items: center; gap: 10px; }',
        '.ai-hdr-title { font-size: 0.98rem; font-weight: 600; margin: 0; display: flex; align-items: center; gap: 6px; }',
        '.ai-hdr-status { font-size: 0.72rem; color: #a3e635; display: flex; align-items: center; gap: 4px; }',
        '.ai-hdr-dot { width: 7px; height: 7px; background: #a3e635; border-radius: 50%; box-shadow: 0 0 6px #a3e635; }',
        '.ai-hdr-actions { display: flex; gap: 8px; }',
        '.ai-hdr-btn { background: rgba(255,255,255,0.15); border: none; color: #ffffff; border-radius: 6px; width: 28px; height: 28px; cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 0.9rem; transition: background 0.15s; }',
        '.ai-hdr-btn:hover { background: rgba(255,255,255,0.3); }',
        '.ai-context-bar { background: #f0f7ff; border-bottom: 1px solid #d0e3ff; padding: 8px 14px; font-size: 0.76rem; color: #005580; display: flex; justify-content: space-between; align-items: center; }',
        '.ai-body { flex: 1; display: flex; flex-direction: column; background: #f8fafc; overflow: hidden; }',
        '.ai-history { flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 12px; }',
        '.ai-msg { padding: 12px 15px; border-radius: 14px; max-width: 88%; font-size: 0.865rem; line-height: 1.5; word-wrap: break-word; }',
        '.ai-u { background: #0088cc; color: #ffffff; align-self: flex-end; border-bottom-right-radius: 4px; box-shadow: 0 2px 8px rgba(0,136,204,0.25); }',
        '.ai-b { background: #ffffff; color: #1e293b; align-self: flex-start; border-bottom-left-radius: 4px; border: 1px solid #e2e8f0; box-shadow: 0 2px 6px rgba(0,0,0,0.04); }',
        '.ai-tool-badge { display: inline-flex; align-items: center; gap: 6px; background: #e0f2fe; color: #0369a1; border: 1px solid #bae6fd; padding: 4px 10px; border-radius: 12px; font-size: 0.75rem; margin-bottom: 8px; animation: aiPulse 1.5s infinite; }',
        '@keyframes aiPulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.65; } }',
        '.ai-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }',
        '.ai-chip { background: #eef2f6; border: 1px solid #cbd5e1; color: #334155; padding: 5px 10px; border-radius: 12px; font-size: 0.76rem; cursor: pointer; transition: all 0.15s; }',
        '.ai-chip:hover { background: #0088cc; color: #ffffff; border-color: #0088cc; transform: translateY(-1px); }',
        '.ai-hitl-box { margin-top: 10px; padding: 10px; background: #fffbeb; border: 1px solid #fef3c7; border-radius: 8px; display: flex; flex-direction: column; gap: 6px; }',
        '.ai-hitl-title { font-size: 0.78rem; font-weight: 600; color: #92400e; }',
        '.ai-hitl-btns { display: flex; gap: 8px; margin-top: 4px; }',
        '.ai-btn-confirm { background: #16a34a; color: #ffffff; border: none; padding: 6px 12px; border-radius: 6px; font-size: 0.78rem; cursor: pointer; font-weight: 600; }',
        '.ai-btn-cancel { background: #dc2626; color: #ffffff; border: none; padding: 6px 12px; border-radius: 6px; font-size: 0.78rem; cursor: pointer; font-weight: 600; }',
        '.ai-row { padding: 12px 14px; background: #ffffff; border-top: 1px solid #e2e8f0; display: flex; gap: 8px; align-items: center; }',
        '.ai-row input { flex: 1; padding: 10px 14px; border: 1px solid #cbd5e1; border-radius: 24px; outline: none; font-size: 0.865rem; transition: border 0.15s; }',
        '.ai-row input:focus { border-color: #0088cc; box-shadow: 0 0 0 3px rgba(0,136,204,0.15); }',
        '.ai-row button { background: #0088cc; color: #ffffff; border: none; border-radius: 50%; width: 40px; height: 40px; cursor: pointer; font-size: 17px; display: flex; justify-content: center; align-items: center; transition: background 0.15s; }',
        '.ai-row button:hover { background: #006699; }',
        '.ai-msg pre { background: #1e293b; color: #f8fafc; padding: 10px 12px; border-radius: 8px; overflow-x: auto; font-size: 0.78rem; position: relative; margin: 8px 0; }',
        '.ai-msg code { font-family: "Consolas", "Monaco", monospace; }',
        '.ai-msg p { margin: 0 0 6px 0; }',
        '.ai-msg p:last-child { margin: 0; }',
        '.ai-msg ul, .ai-msg ol { margin: 6px 0; padding-left: 20px; }',
        '.ai-msg li { margin-bottom: 4px; }',
        '.ai-copy-btn { position: absolute; top: 6px; right: 6px; background: rgba(255,255,255,0.2); border: none; color: #fff; padding: 2px 6px; border-radius: 4px; font-size: 0.68rem; cursor: pointer; }',
        '.ai-cursor { display: inline-block; width: 6px; height: 14px; background: #0088cc; margin-left: 2px; vertical-align: middle; animation: aiBlink 0.8s infinite; }',
        '@keyframes aiBlink { 0%, 100% { opacity: 1; } 50% { opacity: 0.65; } }'
    ].join('');

    function renderMarkdown(text) {
        if (!text) return '';
        var out = text;
        out = out.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        out = out.replace(/```([a-z0-9_\-]*)\n([\s\S]*?)```/gi, function(match, lang, code) {
            return '<pre><button class="ai-copy-btn" onclick="navigator.clipboard.writeText(this.parentElement.querySelector(\'code\').innerText)">Copy</button><code>' + code.trim() + '</code></pre>';
        });
        out = out.replace(/`([^`]+)`/g, '<code>$1</code>');
        out = out.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
        out = out.replace(/\*([^*]+)\*/g, '<em>$1</em>');
        out = out.replace(/^### (.*$)/gim, '<h4 style="margin:8px 0 4px;font-size:0.92rem;color:#0f2b48;">$1</h4>');
        out = out.replace(/^## (.*$)/gim, '<h3 style="margin:10px 0 4px;font-size:0.98rem;color:#0f2b48;">$1</h3>');
        out = out.replace(/^\s*[-•*]\s+(.*)$/gim, '<li>$1</li>');
        out = out.replace(/(<li>.*<\/li>)/gims, '<ul style="margin:6px 0;padding-left:18px;">$1</ul>');
        out = out.replace(/\n\n/g, '<br><br>').replace(/\n/g, '<br>');
        return out;
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
        return { host: host, service: service };
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

        var hdr = document.createElement('div');
        hdr.className = 'ai-hdr';
        hdr.innerHTML = [
            '<div class="ai-hdr-left">',
            '  <div>',
            '    <h3 class="ai-hdr-title">🤖 Icinga AIOps Agent</h3>',
            '    <div class="ai-hdr-status"><span class="ai-hdr-dot"></span> Online &bull; LangGraph + Hybrid RAG</div>',
            '  </div>',
            '</div>',
            '<div class="ai-hdr-actions">',
            '  <button class="ai-hdr-btn" id="ai-clear-btn" title="Clear Chat History">🗑️</button>',
            '  <button class="ai-hdr-btn" id="ai-cls-btn" title="Close">&times;</button>',
            '</div>'
        ].join('');
        panel.appendChild(hdr);

        var ctxBar = document.createElement('div');
        ctxBar.className = 'ai-context-bar';
        ctxBar.id = 'ai-ctx-bar';
        var ctx = getIcingaContext();
        if (ctx.host) {
            ctxBar.innerHTML = '<span>📍 Active: <strong>' + ctx.host + '</strong>' + (ctx.service ? ' &bull; ' + ctx.service : '') + '</span><span style="cursor:pointer;color:#0088cc;" id="ai-ctx-diag">Diagnose</span>';
        } else {
            ctxBar.innerHTML = '<span>🌐 Global Monitoring Overview</span>';
        }
        panel.appendChild(ctxBar);

        var body = document.createElement('div');
        body.className = 'ai-body';
        var hist = document.createElement('div');
        hist.className = 'ai-history';
        hist.id = 'ai-hist';

        var welcomeMsg = document.createElement('div');
        welcomeMsg.className = 'ai-msg ai-b';
        welcomeMsg.innerHTML = [
            '<p>👋 <strong>Hello! I am your Icinga AIOps Agent.</strong></p>',
            '<p style="font-size:0.8rem;color:#64748b;">Powered by LangGraph, OpenSearch logs, and Hybrid RAG runbooks. Ask me to diagnose alerts, check logs, or remediate issues:</p>',
            '<div class="ai-chips">',
            '  <div class="ai-chip" data-q="What are the current critical alerts and failing services?">🚨 Critical Alerts</div>',
            '  <div class="ai-chip" data-q="Give me a high-level system health overview">📊 System Health</div>',
            '  <div class="ai-chip" data-q="Search OpenSearch logs for errors or timeouts in the last 24h">📜 Search Logs</div>',
            '  <div class="ai-chip" data-q="How do I troubleshoot a disk space full exit code 2 alert?">💡 Runbook RCA</div>',
            '</div>'
        ].join('');
        hist.appendChild(welcomeMsg);
        body.appendChild(hist);

        var row = document.createElement('div');
        row.className = 'ai-row';
        var inp = document.createElement('input');
        inp.type = 'text';
        inp.id = 'ai-inp';
        inp.placeholder = 'Ask a question or diagnose an alert...';
        var snd = document.createElement('button');
        snd.id = 'ai-snd';
        snd.innerHTML = '&#10148;';
        row.appendChild(inp);
        row.appendChild(snd);
        body.appendChild(row);
        panel.appendChild(body);

        var fab = document.createElement('button');
        fab.id = 'ai-widget-btn';
        fab.innerHTML = '🤖<div id="ai-widget-badge"></div>';

        wrap.appendChild(panel);
        wrap.appendChild(fab);
        document.body.appendChild(wrap);

        fab.addEventListener('click', function() {
            panel.classList.toggle('ai-open');
            if (panel.classList.contains('ai-open')) {
                var currCtx = getIcingaContext();
                if (currCtx.host) {
                    ctxBar.innerHTML = '<span>📍 Active: <strong>' + currCtx.host + '</strong>' + (currCtx.service ? ' &bull; ' + currCtx.service : '') + '</span><span style="cursor:pointer;color:#0088cc;" id="ai-ctx-diag">Diagnose</span>';
                    var diagBtn = document.getElementById('ai-ctx-diag');
                    if (diagBtn) {
                        diagBtn.addEventListener('click', function() {
                            sendQuery('Diagnose current status and recent logs for host ' + currCtx.host + (currCtx.service ? ' service ' + currCtx.service : ''));
                        });
                    }
                }
                inp.focus();
            }
        });

        document.getElementById('ai-cls-btn').addEventListener('click', function() {
            panel.classList.remove('ai-open');
        });

        document.getElementById('ai-clear-btn').addEventListener('click', function() {
            hist.innerHTML = '';
            hist.appendChild(welcomeMsg);
            SESSION_ID = 'icinga-web-' + Math.random().toString(36).substring(2, 9);
        });

        panel.addEventListener('click', function(e) {
            if (e.target && e.target.classList.contains('ai-chip')) {
                var query = e.target.getAttribute('data-q');
                if (query) sendQuery(query);
            }
            if (e.target && e.target.classList.contains('ai-btn-confirm')) {
                sendQuery('Yes, proceed with the action.');
            }
            if (e.target && e.target.classList.contains('ai-btn-cancel')) {
                sendQuery('No, cancel this action.');
            }
        });

        function sendQuery(qText) {
            var q = (qText || inp.value).trim();
            if (!q) return;

            var activeCtx = getIcingaContext();

            var uMsg = document.createElement('div');
            uMsg.className = 'ai-msg ai-u';
            uMsg.textContent = q;
            hist.appendChild(uMsg);
            inp.value = '';

            var botMsg = document.createElement('div');
            botMsg.className = 'ai-msg ai-b';
            
            var toolBadge = document.createElement('div');
            toolBadge.className = 'ai-tool-badge';
            toolBadge.innerHTML = '⚡ Thinking...';
            botMsg.appendChild(toolBadge);

            var contentDiv = document.createElement('div');
            contentDiv.className = 'ai-content';
            contentDiv.innerHTML = '<span class="ai-cursor"></span>';
            botMsg.appendChild(contentDiv);

            hist.appendChild(botMsg);
            hist.scrollTop = hist.scrollHeight;

            var accumulatedResponse = '';

            fetch(API_BASE + '/api/stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query: q,
                    context: activeCtx,
                    session_id: SESSION_ID
                })
            }).then(function(response) {
                if (!response.ok || !response.body) {
                    throw new Error('Streaming connection failed');
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
                                        toolBadge.innerHTML = d.message || 'Executing ' + d.tool + '...';
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
            }).catch(function(err) {
                fetch(API_BASE + '/api/analyze', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        query: q,
                        context: activeCtx,
                        session_id: SESSION_ID
                    })
                }).then(function(r) { return r.json(); })
                .then(function(data) {
                    toolBadge.style.display = 'none';
                    finalizeResponse(data.response || 'No response returned.');
                }).catch(function() {
                    toolBadge.style.display = 'none';
                    contentDiv.innerHTML = '<span style="color:#dc2626;">❌ Could not connect to AI Agent API at ' + API_BASE + '. Please verify the backend is running.</span>';
                });
            });

            function finalizeResponse(fullText) {
                toolBadge.style.display = 'none';
                contentDiv.innerHTML = renderMarkdown(fullText);

                var lower = fullText.toLowerCase();
                if (lower.indexOf('shall i proceed') !== -1 || lower.indexOf('would you like me to') !== -1 || lower.indexOf('confirm') !== -1) {
                    var hitlBox = document.createElement('div');
                    hitlBox.className = 'ai-hitl-box';
                    hitlBox.innerHTML = [
                        '<div class="ai-hitl-title">⚠️ Action Requires Confirmation</div>',
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
