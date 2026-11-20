/* Interactive horizontal medal tally graphs built with Chart.js.
 * Supports switching between stacked Gold/Silver/Bronze medals and Total Points,
 * toggling individual medal series, live re-sorting, rich hover tooltips, and
 * click-to-inspect delegation details. */
(function () {
    'use strict';

    var COLORS = {
        gold: '#eab308',
        goldHover: '#ca8a04',
        silver: '#94a3b8',
        silverHover: '#64748b',
        bronze: '#f97316',
        bronzeHover: '#ea580c',
        pine: '#116B3B',
        pineHover: '#0C5330'
    };

    function sortRows(rows, sortKey) {
        var copy = rows.slice();
        copy.sort(function (a, b) {
            if (sortKey === 'total') {
                return (b.total - a.total) || (b.gold - a.gold) || (a.rank - b.rank);
            }
            if (sortKey === 'gold') {
                return (b.gold - a.gold) || (b.silver - a.silver) || (b.bronze - a.bronze) || (a.rank - b.rank);
            }
            if (sortKey === 'points') {
                return (Number(b.points) - Number(a.points)) || (a.rank - b.rank);
            }
            return (a.rank - b.rank) || a.name.localeCompare(b.name);
        });
        return copy;
    }

    function buildChart(canvas) {
        var dataEl = document.getElementById(canvas.getAttribute('data-series-id'));
        if (!dataEl) return;

        if (typeof Chart.getChart === 'function') {
            var existing = Chart.getChart(canvas);
            if (existing) existing.destroy();
        }

        var originalRows;
        try {
            originalRows = JSON.parse(dataEl.textContent);
        } catch (error) {
            return;
        }
        if (!originalRows || !originalRows.length) return;

        var wrapper = canvas.closest('[data-medal-chart-wrapper]');
        var stage = wrapper ? wrapper.querySelector('[data-chart-stage]') : canvas.parentElement;
        if (stage) {
            var dynamicHeight = Math.max(220, Math.min(620, originalRows.length * 46 + 68));
            stage.style.height = dynamicHeight + 'px';
        }

        var state = {
            metric: 'medals',
            sort: 'rank',
            visibleSeries: [true, true, true],
            rows: originalRows.slice()
        };

        function makeDatasets() {
            if (state.metric === 'points') {
                return [
                    {
                        label: 'Points',
                        data: state.rows.map(function (row) { return Number(row.points) || 0; }),
                        backgroundColor: COLORS.pine,
                        hoverBackgroundColor: COLORS.pineHover,
                        borderRadius: 6,
                        barThickness: 22,
                        maxBarThickness: 28
                    }
                ];
            }
            return [
                {
                    label: 'Gold',
                    data: state.rows.map(function (row) { return row.gold; }),
                    backgroundColor: COLORS.gold,
                    hoverBackgroundColor: COLORS.goldHover,
                    stack: 'medals',
                    borderRadius: 4,
                    barThickness: 22,
                    maxBarThickness: 28,
                    hidden: !state.visibleSeries[0]
                },
                {
                    label: 'Silver',
                    data: state.rows.map(function (row) { return row.silver; }),
                    backgroundColor: COLORS.silver,
                    hoverBackgroundColor: COLORS.silverHover,
                    stack: 'medals',
                    borderRadius: 4,
                    barThickness: 22,
                    maxBarThickness: 28,
                    hidden: !state.visibleSeries[1]
                },
                {
                    label: 'Bronze',
                    data: state.rows.map(function (row) { return row.bronze; }),
                    backgroundColor: COLORS.bronze,
                    hoverBackgroundColor: COLORS.bronzeHover,
                    stack: 'medals',
                    borderRadius: 4,
                    barThickness: 22,
                    maxBarThickness: 28,
                    hidden: !state.visibleSeries[2]
                }
            ];
        }

        var selectionBox = wrapper ? wrapper.querySelector('[data-chart-selection]') : null;
        var selectionBody = wrapper ? wrapper.querySelector('[data-chart-selection-body]') : null;
        var selectionClear = wrapper ? wrapper.querySelector('[data-chart-selection-clear]') : null;

        function showSelection(row) {
            if (!selectionBox || !selectionBody || !row) return;
            selectionBody.innerHTML =
                '<span class="font-display text-sm font-bold text-ink">#' + row.rank + ' ' + row.name + '</span>' +
                (row.provisional ? '<span class="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-bold text-amber-800">PROV</span>' : '') +
                '<span class="text-slate-300">&middot;</span>' +
                '<span><strong class="text-amber-700">' + row.gold + '</strong> Gold</span>' +
                '<span><strong class="text-slate-600">' + row.silver + '</strong> Silver</span>' +
                '<span><strong class="text-orange-700">' + row.bronze + '</strong> Bronze</span>' +
                '<span class="text-slate-300">&middot;</span>' +
                '<span class="font-bold text-pine-deep">' + row.total + ' medals (' + row.points + ' pts)</span>';
            selectionBox.classList.remove('hidden');
            selectionBox.classList.add('flex');
        }

        if (selectionClear && selectionBox) {
            selectionClear.addEventListener('click', function () {
                selectionBox.classList.add('hidden');
                selectionBox.classList.remove('flex');
            });
        }

        function computeXScale() {
            if (state.metric === 'points') {
                var maxPts = state.rows.reduce(function (acc, row) {
                    return Math.max(acc, Number(row.points) || 0);
                }, 0);
                return {
                    suggestedMax: Math.max(20, Math.ceil((maxPts + 5) / 5) * 5),
                    stepSize: undefined
                };
            }
            var maxMedals = state.rows.reduce(function (acc, row) {
                var sum = (state.visibleSeries[0] ? row.gold : 0)
                    + (state.visibleSeries[1] ? row.silver : 0)
                    + (state.visibleSeries[2] ? row.bronze : 0);
                return Math.max(acc, sum);
            }, 0);
            return {
                suggestedMax: Math.max(5, maxMedals + 2),
                stepSize: maxMedals <= 15 ? 1 : undefined
            };
        }

        var initialScale = computeXScale();

        var chart = new Chart(canvas.getContext('2d'), {
            type: 'bar',
            data: {
                labels: state.rows.map(function (row) { return row.name; }),
                datasets: makeDatasets()
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                animation: { duration: 320 },
                interaction: {
                    mode: 'index',
                    axis: 'y',
                    intersect: false
                },
                onHover: function (event, elements) {
                    if (event && event.native && event.native.target) {
                        event.native.target.style.cursor = elements.length ? 'pointer' : 'default';
                    }
                },
                onClick: function (_event, elements) {
                    if (!elements || !elements.length) return;
                    var idx = elements[0].index;
                    showSelection(state.rows[idx]);
                },
                scales: {
                    x: {
                        stacked: true,
                        beginAtZero: true,
                        suggestedMax: initialScale.suggestedMax,
                        border: { display: false },
                        grid: { color: '#e2e8f0', tickLength: 4 },
                        ticks: {
                            precision: 0,
                            stepSize: initialScale.stepSize,
                            color: '#475569',
                            font: { size: 11, weight: '500' }
                        },
                        title: {
                            display: true,
                            text: 'Medals',
                            color: '#64748b',
                            font: { size: 11, weight: '600' }
                        }
                    },
                    y: {
                        stacked: true,
                        border: { display: false },
                        grid: { display: false },
                        ticks: {
                            color: '#15251B',
                            font: { size: 12, weight: '600' },
                            autoSkip: false,
                            callback: function (value) {
                                var label = this.getLabelForValue(value);
                                return label.length > 26 ? label.slice(0, 25) + '\u2026' : label;
                            }
                        }
                    }
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: '#15251B',
                        titleColor: '#ffffff',
                        bodyColor: '#e2e8f0',
                        footerColor: '#8FE3B4',
                        padding: 12,
                        cornerRadius: 8,
                        displayColors: true,
                        callbacks: {
                            title: function (items) {
                                var row = state.rows[items[0].dataIndex];
                                return '#' + row.rank + ' ' + row.name + (row.provisional ? ' (Provisional)' : '');
                            },
                            label: function (item) {
                                return ' ' + item.dataset.label + ': ' + item.formattedValue;
                            },
                            footer: function (items) {
                                var row = state.rows[items[0].dataIndex];
                                return 'Total: ' + row.total + ' medal' + (row.total === 1 ? '' : 's') + '  \u00b7  ' + row.points + ' pts';
                            }
                        }
                    }
                }
            }
        });

        function refreshChart() {
            state.rows = sortRows(originalRows, state.sort);
            chart.data.labels = state.rows.map(function (row) { return row.name; });
            chart.data.datasets = makeDatasets();
            var isMedals = state.metric === 'medals';
            var xScale = computeXScale();
            chart.options.scales.x.stacked = isMedals;
            chart.options.scales.y.stacked = isMedals;
            chart.options.scales.x.suggestedMax = xScale.suggestedMax;
            chart.options.scales.x.ticks.stepSize = xScale.stepSize;
            chart.options.scales.x.title.text = isMedals ? 'Medals' : 'Points';
            chart.update();
        }

        if (wrapper) {
            var metricButtons = wrapper.querySelectorAll('[data-chart-metric]');
            var medalToggleGroup = wrapper.querySelector('[data-medal-toggles]');

            metricButtons.forEach(function (btn) {
                btn.addEventListener('click', function () {
                    var nextMetric = btn.getAttribute('data-chart-metric');
                    if (nextMetric === state.metric) return;
                    state.metric = nextMetric;

                    metricButtons.forEach(function (b) {
                        var active = b.getAttribute('data-chart-metric') === state.metric;
                        b.setAttribute('aria-pressed', active ? 'true' : 'false');
                        b.classList.toggle('bg-pine', active);
                        b.classList.toggle('text-white', active);
                        b.classList.toggle('text-slate-600', !active);
                    });

                    if (medalToggleGroup) {
                        medalToggleGroup.classList.toggle('hidden', state.metric !== 'medals');
                    }
                    refreshChart();
                });
            });

            wrapper.querySelectorAll('[data-toggle-series]').forEach(function (btn) {
                btn.addEventListener('click', function () {
                    var idx = parseInt(btn.getAttribute('data-toggle-series'), 10);
                    state.visibleSeries[idx] = !state.visibleSeries[idx];
                    // Keep at least one series visible so the chart is never blank.
                    if (!state.visibleSeries[0] && !state.visibleSeries[1] && !state.visibleSeries[2]) {
                        state.visibleSeries[idx] = true;
                        return;
                    }
                    var active = state.visibleSeries[idx];
                    btn.setAttribute('aria-pressed', active ? 'true' : 'false');
                    btn.classList.toggle('opacity-40', !active);
                    btn.classList.toggle('line-through', !active);
                    refreshChart();
                });
            });

            var sortSelect = wrapper.querySelector('[data-chart-sort]');
            if (sortSelect) {
                sortSelect.addEventListener('change', function () {
                    state.sort = sortSelect.value;
                    refreshChart();
                });
            }
        }
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
