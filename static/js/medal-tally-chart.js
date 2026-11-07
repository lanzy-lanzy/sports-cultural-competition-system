/* Draws the medal tally bar graphs with the vendored Chart.js library.
 * Each canvas[data-medal-chart] points at a json_script payload through
 * data-series-id; gold/silver/bronze stack on a shared y-axis scale so the
 * team and individual graphs stay comparable side by side. */
(function () {
    'use strict';

    var COLORS = { gold: '#facc15', silver: '#94a3b8', bronze: '#fb923c' };

    function buildChart(canvas) {
        var dataEl = document.getElementById(canvas.getAttribute('data-series-id'));
        if (!dataEl) return;

        if (typeof Chart.getChart === 'function') {
            var existing = Chart.getChart(canvas);
            if (existing) existing.destroy();
        }

        var rows;
        try {
            rows = JSON.parse(dataEl.textContent);
        } catch (error) {
            return;
        }
        if (!rows || !rows.length) return;

        var chartMax = parseInt(canvas.getAttribute('data-chart-max'), 10) || 0;

        new Chart(canvas.getContext('2d'), {
            type: 'bar',
            data: {
                labels: rows.map(function (row) { return row.name; }),
                datasets: [
                    { label: 'Gold', data: rows.map(function (row) { return row.gold; }), backgroundColor: COLORS.gold, stack: 'medals', borderRadius: 2 },
                    { label: 'Silver', data: rows.map(function (row) { return row.silver; }), backgroundColor: COLORS.silver, stack: 'medals', borderRadius: 2 },
                    { label: 'Bronze', data: rows.map(function (row) { return row.bronze; }), backgroundColor: COLORS.bronze, stack: 'medals', borderRadius: 2 }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: { duration: 300 },
                scales: {
                    x: {
                        stacked: true,
                        grid: { display: false },
                        ticks: {
                            color: '#475569',
                            font: { size: 10 },
                            autoSkip: false,
                            maxRotation: 60,
                            minRotation: 45,
                            callback: function (value) {
                                var label = this.getLabelForValue(value);
                                return label.length > 14 ? label.slice(0, 13) + '...' : label;
                            }
                        }
                    },
                    y: {
                        stacked: true,
                        beginAtZero: true,
                        suggestedMax: chartMax || undefined,
                        max: chartMax || undefined,
                        grid: { color: '#e2e8f0' },
                        ticks: { precision: 0, color: '#475569', font: { size: 10 } },
                        title: { display: true, text: 'Medals', color: '#64748b', font: { size: 11 } }
                    }
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            title: function (items) {
                                var row = rows[items[0].dataIndex];
                                return row.rank + '. ' + row.name + (row.provisional ? ' (provisional)' : '');
                            },
                            label: function (item) {
                                return ' ' + item.dataset.label + ': ' + item.formattedValue;
                            },
                            footer: function (items) {
                                var row = rows[items[0].dataIndex];
                                return 'Total: ' + row.total + ' medals / ' + row.points + ' pts';
                            }
                        }
                    }
                }
            }
        });
    }

    function init() {
        if (typeof Chart === 'undefined') {
            document.querySelectorAll('[data-medal-chart]').forEach(function (canvas) {
                var fallback = canvas.parentElement;
                fallback.innerHTML = '<p class="flex h-full items-center justify-center rounded-md border border-dashed border-slate-200 bg-slate-50 text-sm text-slate-500">Chart could not be loaded. Medal totals remain available in the table below.</p>';
            });
            return;
        }
        document.querySelectorAll('canvas[data-medal-chart]').forEach(buildChart);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();