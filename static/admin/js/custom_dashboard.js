/* Renders the two small sparkline charts on the admin dashboard.
   Called from admin/index.html once Chart.js + the data are loaded. */

window.initDrDashboardCharts = function (data) {
    if (typeof Chart === 'undefined') return;

    var labels = ['6d', '5d', '4d', '3d', '2d', 'Yesterday', 'Today'];

    var salesCanvas = document.getElementById('dr-sales-chart');
    if (salesCanvas && data.dailySales) {
        new Chart(salesCanvas, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    data: data.dailySales,
                    borderColor: '#16241C',
                    backgroundColor: 'rgba(22, 36, 28, 0.08)',
                    fill: true,
                    tension: 0.35,
                    pointRadius: 0,
                    borderWidth: 2
                }]
            },
            options: {
                plugins: { legend: { display: false } },
                scales: { x: { display: false }, y: { display: false } },
                elements: { line: { borderJoinStyle: 'round' } }
            }
        });
    }

    var ordersCanvas = document.getElementById('dr-orders-chart');
    if (ordersCanvas && data.dailyOrders) {
        new Chart(ordersCanvas, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    data: data.dailyOrders,
                    borderColor: '#C8912E',
                    backgroundColor: 'rgba(200, 145, 46, 0.1)',
                    fill: true,
                    tension: 0.35,
                    pointRadius: 0,
                    borderWidth: 2
                }]
            },
            options: {
                plugins: { legend: { display: false } },
                scales: { x: { display: false }, y: { display: false } },
                elements: { line: { borderJoinStyle: 'round' } }
            }
        });
    }
};