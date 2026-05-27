// State
let anomalyEnabled = false;
let currentData = [];
let currentColumns = [];
let currentSQL = '';
let currentChart = null;
let isStreaming = false;

// Session ID — generated once per browser session
if (!window.__sessionId) {
    window.__sessionId = 'sess_' + Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
}
const SESSION_ID = window.__sessionId;

function toggleAnomaly() {
    anomalyEnabled = !anomalyEnabled;
    const btn = document.getElementById('anomalyBtn');
    const status = document.getElementById('anomalyStatus');
    btn.classList.toggle('active', anomalyEnabled);
    status.classList.toggle('active', anomalyEnabled);
    status.textContent = anomalyEnabled ? '异常检测: 开启' : '异常检测: 关闭';
}

function askSuggestion(el) {
    const text = el.textContent || el.innerText;
    document.getElementById('chatInput').value = text;
    sendMessage();
}

function switchTab(tabName, btn) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById(tabName + 'View').classList.add('active');
    if (tabName === 'chart' && currentChart) {
        setTimeout(() => {
            const container = document.getElementById('chartContainer');
            if (container.offsetWidth > 0) currentChart.resize();
        }, 100);
    }
}

function showApiDocs() {
    window.open('/docs', '_blank');
}

function copySQL() {
    navigator.clipboard.writeText(currentSQL).then(() => {
        const btn = document.querySelector('.sql-header button');
        btn.textContent = '已复制';
        setTimeout(() => btn.textContent = '复制', 1500);
    });
}

function exportCSV() {
    if (!currentData.length) return;
    const header = currentColumns.join(',');
    const rows = currentData.map(row =>
        currentColumns.map(col => {
            let val = row[col];
            if (val === null || val === undefined) return '';
            if (typeof val === 'string' && (val.includes(',') || val.includes('"') || val.includes('\n'))) {
                return '"' + val.replace(/"/g, '""') + '"';
            }
            return val;
        }).join(',')
    );
    const csv = '﻿' + header + '\n' + rows.join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = 'data_export.csv';
    link.click();
    URL.revokeObjectURL(link.href);
}

function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
}

function autoResize(textarea) {
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
}

document.addEventListener('DOMContentLoaded', () => {
    const input = document.getElementById('chatInput');
    input.addEventListener('input', () => autoResize(input));
});

async function clearHistory() {
    await fetch('/api/chat/history', {
        method: 'DELETE',
        headers: { 'X-Session-ID': SESSION_ID },
    });
    const messages = document.getElementById('chatMessages');
    messages.innerHTML = '';
    document.getElementById('emptyState').style.display = 'flex';
    document.getElementById('dataContent').style.display = 'none';
    currentData = [];
    currentColumns = [];
    currentSQL = '';
}
