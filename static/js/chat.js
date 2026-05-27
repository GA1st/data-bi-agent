async function sendMessage() {
    const input = document.getElementById('chatInput');
    const message = input.value.trim();
    if (!message || isStreaming) return;

    input.value = '';
    autoResize(input);
    isStreaming = true;
    document.getElementById('sendBtn').disabled = true;

    const msgArea = document.getElementById('chatMessages');
    const welcome = msgArea.querySelector('.welcome-message');
    if (welcome) welcome.remove();

    addMessage('user', message);
    const aiMsgId = addMessage('ai', '', true);

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-Session-ID': SESSION_ID },
            body: JSON.stringify({ message, enable_anomaly: anomalyEnabled }),
        });
        if (!response.ok) throw new Error('请求失败: ' + response.status);

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '', fullText = '';

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
                } catch (e) {}
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
        case 'status': setStatus(aiMsgId, data.message); break;
        case 'sql':
            currentSQL = data.sql; currentQuestion = document.getElementById('chatInput').value || currentQuestion;
            showSQL(data.sql);
            if (data.explanation) { fullText += data.explanation + '\n\n'; updateMessage(aiMsgId, fullText); }
            break;
        case 'sql_fixed':
            currentSQL = data.sql; showSQL(data.sql);
            fullText += 'SQL已修复: ' + (data.explanation || '') + '\n\n'; updateMessage(aiMsgId, fullText);
            break;
        case 'data':
            currentData = data.all_data || data.data;
            currentColumns = data.columns;
            showDataTable(data.data, data.columns, data.row_count);
            document.getElementById('resultEmpty').style.display = 'none';
            document.getElementById('resultContent').style.display = 'flex';
            break;
        case 'chart':
            if (data.chart && data.chart.chart_type !== 'none' && data.chart.config) {
                showChart(data.chart.config);
                document.querySelectorAll('.rtab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.rtab')[1].classList.add('active');
                document.getElementById('chartView').classList.add('active');
            }
            break;
        case 'anomaly':
            break;
        case 'explanation': fullText += data.message; updateMessage(aiMsgId, fullText); break;
        case 'error': fullText += '\n\n' + data.message; updateMessage(aiMsgId, fullText); break;
        case 'done': break;
    }
    return fullText;
}

function addMessage(role, content, showTyping = false) {
    const c = document.getElementById('chatMessages');
    const id = 'msg-' + Date.now();
    const div = document.createElement('div');
    if (role === 'user') {
        div.className = 'msg msg-user';
        div.innerHTML = `<div class="bubble">${escapeHtml(content)}</div>`;
    } else {
        div.className = 'msg msg-ai'; div.id = id;
        div.innerHTML = `<div class="avatar">AI</div><div class="bubble">${showTyping ? '<div class="typing-indicator"><span></span><span></span><span></span></div>' : ''}<div class="msg-content">${content ? renderMd(content) : ''}</div></div>`;
    }
    c.appendChild(div); c.scrollTop = c.scrollHeight;
    return id;
}
function updateMessage(id, content) {
    const el = document.getElementById(id); if (!el) return;
    const c = el.querySelector('.msg-content'); if (c) c.innerHTML = renderMd(content);
    document.getElementById('chatMessages').scrollTop = 999999;
}
function setStatus(id, s) {
    const el = document.getElementById(id); if (!el) return;
    const c = el.querySelector('.msg-content');
    if (c) c.innerHTML = `<span style="color:var(--text-muted);font-size:12px">${escapeHtml(s)}</span>`;
}
function removeTyping(id) {
    const el = document.getElementById(id); if (!el) return;
    const t = el.querySelector('.typing-indicator'); if (t) t.remove();
}
function renderMd(t) {
    if (typeof marked !== 'undefined') { try { return marked.parse(t); } catch (e) {} }
    return t.replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\n/g, '<br>');
}
function showSQL(sql) {
    document.getElementById('sqlDisplay').style.display = 'block';
    document.getElementById('sqlCode').textContent = sql;
}
function showDataTable(data, columns, total) {
    document.getElementById('resultInfo').textContent = `${total} 行`;
    const c = document.getElementById('tableContainer');
    if (!data.length) { c.innerHTML = '<p style="text-align:center;color:var(--text-muted);padding:40px">无数据</p>'; return; }
    let h = '<table><thead><tr>';
    columns.forEach(col => { h += `<th>${escapeHtml(col)}</th>`; });
    h += '</tr></thead><tbody>';
    data.forEach(row => {
        h += '<tr>';
        columns.forEach(col => {
            const v = row[col]; const isNum = typeof v === 'number';
            h += `<td class="${isNum ? 'num' : ''}">${v === null ? '-' : escapeHtml(String(v))}</td>`;
        });
        h += '</tr>';
    });
    c.innerHTML = h + '</tbody></table>';
}
function showChart(config) {
    if (currentChart) { currentChart.dispose(); currentChart = null; }
    const darkConfig = {
        backgroundColor: 'transparent',
        textStyle: { color: '#94a3b8' },
        title: { textStyle: { color: '#f1f5f9' } },
        legend: { textStyle: { color: '#94a3b8' } },
        tooltip: { backgroundColor: '#1e293b', borderColor: '#334155', textStyle: { color: '#f1f5f9' } },
        ...config,
    };
    currentChart = echarts.init(document.getElementById('chartContainer'));
    currentChart.setOption(darkConfig);
    window.addEventListener('resize', () => { if (currentChart) currentChart.resize(); });
}
