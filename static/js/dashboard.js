function showDataTable(data, columns, totalCount) {
    const container = document.getElementById('tableContainer');
    document.getElementById('resultInfo').textContent =
        `${totalCount} 行${totalCount !== data.length ? ` (显示前 ${data.length} 行)` : ''}`;

    if (!data.length) {
        container.innerHTML = '<p style="text-align:center;color:var(--text-muted);padding:40px;">查询无数据</p>';
        return;
    }

    let html = '<table><thead><tr>';
    columns.forEach(col => {
        html += `<th>${escapeHtml(col)}</th>`;
    });
    html += '</tr></thead><tbody>';

    data.forEach(row => {
        html += '<tr>';
        columns.forEach(col => {
            const val = row[col];
            const isNum = typeof val === 'number';
            const display = val === null || val === undefined ? '-' : val;
            html += `<td class="${isNum ? 'number' : ''}">${escapeHtml(String(display))}</td>`;
        });
        html += '</tr>';
    });

    html += '</tbody></table>';
    container.innerHTML = html;
}

function showChart(config) {
    const container = document.getElementById('chartContainer');

    if (currentChart) {
        currentChart.dispose();
        currentChart = null;
    }

    // Apply dark theme
    const darkConfig = {
        backgroundColor: 'transparent',
        textStyle: { color: '#94a3b8' },
        title: { textStyle: { color: '#f1f5f9' } },
        legend: { textStyle: { color: '#94a3b8' } },
        tooltip: {
            backgroundColor: '#1e293b',
            borderColor: '#334155',
            textStyle: { color: '#f1f5f9' },
        },
        ...config,
    };

    // Ensure grid has enough bottom margin for labels
    if (darkConfig.xAxis && darkConfig.xAxis.data && darkConfig.xAxis.data.length > 8) {
        darkConfig.grid = darkConfig.grid || {};
        darkConfig.grid.bottom = darkConfig.grid.bottom || 80;
        darkConfig.xAxis.axisLabel = darkConfig.xAxis.axisLabel || {};
        darkConfig.xAxis.axisLabel.rotate = darkConfig.xAxis.axisLabel.rotate || 30;
    }

    currentChart = echarts.init(container, null, { renderer: 'canvas' });
    currentChart.setOption(darkConfig);

    window.addEventListener('resize', () => {
        if (currentChart) currentChart.resize();
    });
}

function showAnomalyAlert(anomalyResult) {
    const reportContainer = document.getElementById('reportContainer');
    let html = '<div class="anomaly-alert">';
    html += `<h4>检测到 ${anomalyResult.anomaly_count} 个数据异常</h4>`;
    html += '<ul>';
    anomalyResult.anomalies.slice(5).forEach(a => {
        html += `<li><strong>${a.column}</strong>: 值 ${a.value} (${a.method}: ${a.reason})</li>`;
    });
    html += '</ul>';
    if (anomalyResult.summary) {
        html += `<p style="margin-top:8px;font-size:12px;color:var(--text-muted);">${escapeHtml(anomalyResult.summary)}</p>`;
    }
    html += '</div>';
    reportContainer.innerHTML = html;

    // Switch to report tab
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab')[2].classList.add('active');
    document.getElementById('reportView').classList.add('active');
}

// Report generation via dashboard API
async function loadDashboardReport() {
    const reportContainer = document.getElementById('reportContainer');
    reportContainer.innerHTML = '<p style="text-align:center;color:var(--text-muted);padding:40px;">正在生成报告...</p>';

    try {
        const res = await fetch('/api/dashboard/report');
        const report = await res.json();

        let html = '';

        // KPIs
        if (report.kpis) {
            html += '<div class="report-kpis">';
            html += kpiCard(report.kpis.total_revenue, '总收入');
            html += kpiCard(report.kpis.total_orders, '总订单');
            html += kpiCard(report.kpis.total_customers, '总客户');
            html += kpiCard(report.kpis.avg_order_amount, '平均客单价');
            html += kpiCard(report.kpis.month_revenue, '本月收入');
            html += kpiCard(report.kpis.cancel_rate, '取消率(%)');
            html += '</div>';
        }

        // Narrative
        if (report.narrative) {
            html += `<div class="report-section"><h3>经营分析摘要</h3><div class="narrative">${renderMarkdown(report.narrative)}</div></div>`;
        }

        // Anomalies
        if (report.anomalies && report.anomalies.details && report.anomalies.details.length > 0) {
            html += '<div class="anomaly-alert">';
            html += `<h4>${report.anomalies.status}</h4><ul>`;
            report.anomalies.details.forEach(d => {
                html += `<li>${d.date}: 收入 ${d.revenue} (${d.deviation})</li>`;
            });
            html += '</ul></div>';
        }

        reportContainer.innerHTML = html;

        // Show charts in chart tab if we have them
        if (report.charts) {
            document.getElementById('emptyState').style.display = 'none';
            document.getElementById('dataContent').style.display = 'flex';

            if (report.charts.trend) {
                currentColumns = ['月份', '收入', '订单数'];
                showChart(report.charts.trend);
            }
        }
    } catch (err) {
        reportContainer.innerHTML = `<p style="text-align:center;color:var(--error);padding:40px;">报告生成失败: ${err.message}</p>`;
    }
}

function kpiCard(value, label) {
    const formatted = typeof value === 'number'
        ? (value >= 10000 ? (value / 10000).toFixed(1) + '万' : value.toLocaleString())
        : (value || '-');
    return `<div class="kpi-card"><div class="kpi-value">${formatted}</div><div class="kpi-label">${label}</div></div>`;
}
