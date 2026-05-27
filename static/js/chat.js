async function sendMessage() {
    const input = document.getElementById('chatInput');
    const message = input.value.trim();
    if (!message || isStreaming) return;

    input.value = '';
    autoResize(input);
    isStreaming = true;
    document.getElementById('sendBtn').disabled = true;

    // Hide welcome, show user message
    hideWelcome();
    addMessage('user', message);

    // Add AI placeholder
    const aiMsgId = addMessage('ai', '', true);

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Session-ID': SESSION_ID,
            },
            body: JSON.stringify({ message, enable_anomaly: anomalyEnabled }),
        });

        if (!response.ok) throw new Error('请求失败: ' + response.status);

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let fullText = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                if (!line.trim()) continue;
                try {
                    const data = JSON.parse(line);
                    fullText = handleStreamEvent(data, aiMsgId, fullText);
                } catch (e) {
                    // skip non-json lines
                }
            }
        }
    } catch (err) {
        updateMessage(aiMsgId, '请求失败: ' + err.message);
    } finally {
        removeTyping(aiMsgId);
        isStreaming = false;
        document.getElementById('sendBtn').disabled = false;
    }
}

function handleStreamEvent(data, aiMsgId, fullText) {
    switch (data.type) {
        case 'status':
            setStatus(aiMsgId, data.message);
            break;

        case 'sql':
            currentSQL = data.sql;
            showSQL(data.sql);
            if (data.explanation) {
                fullText += data.explanation + '\n\n';
                updateMessage(aiMsgId, fullText);
            }
            break;

        case 'sql_fixed':
            currentSQL = data.sql;
            showSQL(data.sql);
            fullText += 'SQL已自动修复: ' + (data.explanation || '') + '\n\n';
            updateMessage(aiMsgId, fullText);
            break;

        case 'data':
            currentData = data.all_data || data.data;
            currentColumns = data.columns;
            showDataTable(data.data, data.columns, data.row_count);
            document.getElementById('emptyState').style.display = 'none';
            document.getElementById('dataContent').style.display = 'flex';
            break;

        case 'chart':
            if (data.chart && data.chart.chart_type !== 'none' && data.chart.config) {
                showChart(data.chart.config);
                // Switch to chart tab
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.tab')[1].classList.add('active');
                document.getElementById('chartView').classList.add('active');
            }
            break;

        case 'anomaly':
            if (data.anomaly && data.anomaly.has_anomaly) {
                showAnomalyAlert(data.anomaly);
            }
            break;

        case 'explanation':
            fullText += data.message;
            updateMessage(aiMsgId, fullText);
            break;

        case 'error':
            fullText += '\n\n' + data.message;
            updateMessage(aiMsgId, fullText);
            break;

        case 'done':
            break;
    }
    return fullText;
}

function hideWelcome() {
    const welcome = document.querySelector('.welcome-message');
    if (welcome) welcome.style.display = 'none';
}

function addMessage(role, content, showTyping = false) {
    const container = document.getElementById('chatMessages');
    const id = 'msg-' + Date.now();
    const div = document.createElement('div');

    if (role === 'user') {
        div.className = 'msg msg-user';
        div.innerHTML = `<div class="bubble">${escapeHtml(content)}</div>`;
    } else {
        div.className = 'msg msg-ai';
        div.id = id;
        div.innerHTML = `
            <div class="avatar">AI</div>
            <div class="bubble">
                ${showTyping ? '<div class="typing-indicator"><span></span><span></span><span></span></div>' : ''}
                <div class="msg-content">${content ? renderMarkdown(content) : ''}</div>
            </div>
        `;
    }

    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    return id;
}

function updateMessage(id, content) {
    const el = document.getElementById(id);
    if (!el) return;
    const contentEl = el.querySelector('.msg-content');
    if (contentEl) contentEl.innerHTML = renderMarkdown(content);
    const container = document.getElementById('chatMessages');
    container.scrollTop = container.scrollHeight;
}

function setStatus(id, status) {
    const el = document.getElementById(id);
    if (!el) return;
    const contentEl = el.querySelector('.msg-content');
    if (contentEl) contentEl.innerHTML = `<span style="color: var(--text-muted); font-size: 12px;">${escapeHtml(status)}</span>`;
}

function removeTyping(id) {
    const el = document.getElementById(id);
    if (!el) return;
    const typing = el.querySelector('.typing-indicator');
    if (typing) typing.remove();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function renderMarkdown(text) {
    if (typeof marked !== 'undefined') {
        try {
            return marked.parse(text);
        } catch (e) {}
    }
    return text.replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\n/g, '<br>');
}

function showSQL(sql) {
    const display = document.getElementById('sqlDisplay');
    const code = document.getElementById('sqlCode');
    display.style.display = 'block';
    code.textContent = sql;
}
