// --- Dashboard ---
async function refreshDashboard() {
    const c = document.getElementById('dashboardContent');
    c.innerHTML = '<div class="loading">加载中...</div>';
    try {
        const res = await fetch('/api/dashboard/report');
        const r = await res.json();
        renderDashboard(r);
    } catch (e) {
        c.innerHTML = `<div class="loading">加载失败: ${e.message}</div>`;
    }
}

function renderDashboard(r) {
    const c = document.getElementById('dashboardContent');
    let html = '';

    // KPI cards
    if (r.kpis) {
        html += '<div class="kpi-grid">';
        html += kpi('总收入', r.kpis.total_revenue, 'c1', '所有有效订单');
        html += kpi('本月收入', r.kpis.month_revenue, 'c2', `${r.kpis.month_orders || '-'} 笔订单`);
        html += kpi('总订单', r.kpis.total_orders, 'c3', '有效订单');
        html += kpi('客户数', r.kpis.total_customers, 'c4', '注册客户');
        html += kpi('客单价', r.kpis.avg_order_amount, 'c5', '平均订单金额');
        html += kpi('取消率', r.kpis.cancel_rate + '%', 'c6', '订单取消比例');
        html += '</div>';
    }

    // Charts
    html += '<div class="charts-grid">';
    if (r.charts) {
        html += '<div class="chart-card"><h3>月度趋势</h3><div class="echarts-container" id="dashTrend"></div></div>';
        html += '<div class="chart-card"><h3>区域分布</h3><div class="echarts-container" id="dashRegion"></div></div>';
        html += '<div class="chart-card" style="grid-column:span 2"><h3>TOP10 产品</h3><div class="echarts-container" id="dashProducts"></div></div>';
    }
    html += '</div>';

    // Anomalies
    if (r.anomalies && r.anomalies.details && r.anomalies.details.length > 0) {
        html += '<div class="alert-card"><h3>⚠ 异常检测</h3><ul>';
        r.anomalies.details.forEach(d => { html += `<li>${d.date}: 收入 ${formatNum(d.revenue)} (${d.deviation})</li>`; });
        html += '</ul></div>';
    }

    // Narrative
    if (r.narrative) {
        html += `<div class="narrative-card"><h3>AI 经营分析</h3>${renderMd(r.narrative)}</div>`;
    }

    c.innerHTML = html;

    // Render charts
    if (r.charts) {
        if (r.charts.trend) initDashChart('dashTrend', r.charts.trend);
        if (r.charts.region) initDashChart('dashRegion', r.charts.region);
        if (r.charts.top_products) initDashChart('dashProducts', r.charts.top_products);
    }
}

function kpi(label, value, cls, sub) {
    return `<div class="kpi-card ${cls}"><div class="kpi-label">${label}</div><div class="kpi-value">${formatNum(value)}</div><div class="kpi-sub">${sub}</div></div>`;
}

const _dashCharts = {};
function initDashChart(id, config) {
    const el = document.getElementById(id);
    if (!el) return;
    if (_dashCharts[id]) _dashCharts[id].dispose();
    _dashCharts[id] = echarts.init(el);
    _dashCharts[id].setOption({
        backgroundColor: 'transparent',
        textStyle: { color: '#94a3b8' },
        legend: { textStyle: { color: '#94a3b8' } },
        tooltip: { backgroundColor: '#1e293b', borderColor: '#334155', textStyle: { color: '#f1f5f9' } },
        ...config,
    });
}

// --- Explorer ---
async function loadExplorer() {
    const sidebar = document.getElementById('tableList');
    sidebar.innerHTML = '<div class="loading">加载中...</div>';
    try {
        const res = await fetch('/api/tables');
        const data = await res.json();
        sidebar.innerHTML = '';
        data.tables.forEach(t => {
            const btn = document.createElement('button');
            btn.className = 'table-item';
            btn.innerHTML = `<span>${t.name}</span><span class="row-count">${t.row_count}</span>`;
            btn.onclick = () => selectTable(t.name, btn);
            sidebar.appendChild(btn);
        });
    } catch (e) {
        sidebar.innerHTML = `<div class="loading">加载失败</div>`;
    }
}

async function selectTable(name, btn) {
    document.querySelectorAll('.table-item').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const main = document.getElementById('explorerMain');
    main.innerHTML = '<div class="loading">加载中...</div>';

    try {
        const [schemaRes, dataRes] = await Promise.all([
            fetch(`/api/dashboard/tables/${name}/schema`),
            fetch(`/api/tables/${name}/data?page=1&page_size=50`),
        ]);
        const schema = await schemaRes.json();
        const tableData = await dataRes.json();

        let html = `<div class="explorer-table-info"><h2>${name}</h2>
            <div class="column-grid">`;
        schema.columns.forEach(col => {
            const attrs = [];
            if (col.primary_key) attrs.push('PK');
            if (!col.nullable) attrs.push('NOT NULL');
            html += `<div class="column-card"><div class="col-name">${col.name}</div><div class="col-type">${col.type}</div>${attrs.length ? `<div class="col-attrs">${attrs.join(' · ')}</div>` : ''}</div>`;
        });
        html += '</div></div>';

        html += `<div style="margin-top:16px"><h3 style="font-size:14px;color:var(--text-secondary);margin-bottom:8px">数据预览 (${tableData.total} 行)</h3>`;
        html += '<div class="table-container"><table><thead><tr>';
        tableData.columns.forEach(col => { html += `<th>${col}</th>`; });
        html += '</tr></thead><tbody>';
        tableData.data.forEach(row => {
            html += '<tr>';
            tableData.columns.forEach(col => {
                const v = row[col]; const isNum = typeof v === 'number';
                html += `<td class="${isNum ? 'num' : ''}">${v === null ? '-' : escapeHtml(String(v))}</td>`;
            });
            html += '</tr>';
        });
        html += '</tbody></table></div></div>';

        main.innerHTML = html;
    } catch (e) {
        main.innerHTML = `<div class="loading">加载失败: ${e.message}</div>`;
    }
}

// --- Saved Queries ---
async function loadSavedQueries() {
    const c = document.getElementById('savedContent');
    try {
        const res = await fetch('/api/saved-queries');
        const data = await res.json();
        if (!data.queries || data.queries.length === 0) {
            c.innerHTML = '<div class="explorer-empty">暂无保存的查询。在 AI 对话中点击"保存查询"添加。</div>';
            return;
        }
        let html = '<div class="saved-grid">';
        data.queries.forEach(q => {
            const safeId = q.id;
            html += `<div class="saved-card" data-query-id="${safeId}">
                <h3>${escapeHtml(q.name)}</h3>
                <div class="saved-question">${escapeHtml(q.question)}</div>
                <div class="saved-sql">${escapeHtml(q.sql)}</div>
                <div class="saved-actions">
                    <button class="action-btn delete-btn" data-id="${safeId}">删除</button>
                </div>
            </div>`;
        });
        html += '</div>';
        c.innerHTML = html;
        // Event delegation for saved queries
        c.querySelectorAll('.saved-card').forEach(card => {
            card.addEventListener('click', () => {
                const id = card.dataset.queryId;
                const q = data.queries.find(q => q.id == id);
                if (q) runSavedQuery(q.sql, q.question);
            });
        });
        c.querySelectorAll('.delete-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                deleteSavedQuery(parseInt(btn.dataset.id));
            });
        });
    } catch (e) {
        c.innerHTML = `<div class="loading">加载失败</div>`;
    }
}

function runSavedQuery(sql, question) {
    navigate('chat');
    document.getElementById('chatInput').value = question;
    setTimeout(() => sendMessage(), 100);
}

async function deleteSavedQuery(id) {
    try {
        const res = await fetch(`/api/saved-queries/${id}`, { method: 'DELETE' });
        if (!res.ok) throw new Error('删除失败');
    } catch (e) {
        alert('删除失败: ' + e.message);
    }
    loadSavedQueries();
}
