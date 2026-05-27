// State
let anomalyEnabled = false;
let currentData = [];
let currentColumns = [];
let currentSQL = '';
let currentQuestion = '';
let currentChart = null;
let isStreaming = false;

if (!window.__sessionId) {
    window.__sessionId = 'sess_' + Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
}
const SESSION_ID = window.__sessionId;

// Navigation
function navigate(page) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-item[data-page]').forEach(n => n.classList.remove('active'));
    document.getElementById('page-' + page).classList.add('active');
    document.querySelector(`.nav-item[data-page="${page}"]`).classList.add('active');
    if (page === 'dashboard') refreshDashboard();
    if (page === 'explorer') loadExplorer();
    if (page === 'saved') loadSavedQueries();
}

function toggleAnomaly() {
    anomalyEnabled = !anomalyEnabled;
    const btn = document.getElementById('anomalyBtn');
    const status = document.getElementById('anomalyStatus');
    btn.classList.toggle('warning', anomalyEnabled);
    btn.classList.toggle('active', anomalyEnabled);
    status.textContent = anomalyEnabled ? '异常: 开' : '异常检测';
}

function askSuggestion(el) {
    navigate('chat');
    const text = el.textContent || el.innerText;
    document.getElementById('chatInput').value = text;
    setTimeout(() => sendMessage(), 100);
}

function switchTab(name, btn) {
    document.querySelectorAll('.rtab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById(name + 'View').classList.add('active');
    if (name === 'chart' && currentChart) {
        setTimeout(() => { if (currentChart) currentChart.resize(); }, 50);
    }
}

function copySQL() {
    navigator.clipboard.writeText(currentSQL);
    const btn = document.querySelector('.copy-btn');
    btn.textContent = '已复制';
    setTimeout(() => btn.textContent = '复制', 1500);
}

function exportCSV() {
    if (!currentData.length) return;
    const header = currentColumns.join(',');
    const rows = currentData.map(row =>
        currentColumns.map(col => {
            let val = row[col];
            if (val === null || val === undefined) return '';
            if (typeof val === 'string' && (val.includes(',') || val.includes('"')))
                return '"' + val.replace(/"/g, '""') + '"';
            return val;
        }).join(',')
    );
    const csv = '﻿' + header + '\n' + rows.join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'data_export.csv';
    a.click();
}

function saveCurrentQuery() {
    if (!currentSQL || !currentQuestion) return;
    const name = prompt('为这个查询命名:', currentQuestion);
    if (!name) return;
    fetch('/api/saved-queries', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Session-ID': SESSION_ID },
        body: JSON.stringify({ name, question: currentQuestion, sql: currentSQL }),
    }).then(() => alert('已保存'));
}

function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
}

function autoResize(ta) { ta.style.height = 'auto'; ta.style.height = Math.min(ta.scrollHeight, 100) + 'px'; }

document.addEventListener('DOMContentLoaded', () => {
    const input = document.getElementById('chatInput');
    input.addEventListener('input', () => autoResize(input));
    refreshDashboard();
});

function escapeHtml(t) { const d = document.createElement('div'); d.textContent = t; return d.innerHTML; }

function formatNum(n) {
    if (n === null || n === undefined) return '-';
    if (typeof n !== 'number') return n;
    if (n >= 100000000) return (n / 100000000).toFixed(2) + '亿';
    if (n >= 10000) return (n / 10000).toFixed(1) + '万';
    return n.toLocaleString();
}
