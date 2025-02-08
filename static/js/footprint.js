function updateData() {
    document.getElementById('co2-emissions').textContent = Math.floor(Math.random() * 5000) + 1000;
    document.getElementById('fuel-consumption').textContent = Math.floor(Math.random() * 1000) + 500;
    document.getElementById('energy-consumption').textContent = Math.floor(Math.random() * 5000) + 2000;
    document.getElementById('distance-traveled').textContent = Math.floor(Math.random() * 50) + 10;
}

const ctx1 = document.getElementById('carbonTrendChart').getContext('2d');
new Chart(ctx1, {
    type: 'line',
    data: {
        labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun','July','Aug','Sept','Nov','Dec'],
        datasets: [{
            label: 'Monthly CO₂ Emissions',
            data: [120, 110, 140, 130, 150, 160, 140, 155, 150, 115, 100,120],
            borderColor: 'green',
            borderWidth: 2,
            fill: false,
            pointRadius: 5,
            pointHoverRadius: 8
        }]
    },
    options: {
        responsive: true,
        plugins: {
            tooltip: {
                enabled: true
            }
        }
    }
});

const ctx2 = document.getElementById('energyChart').getContext('2d');
new Chart(ctx2, {
    type: 'bar',
    data: {
        labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun','July','Aug','Sept','Nov','Dec'],
        datasets: [{
            label: 'Energy Consumption (MJ)',
            data: [300, 450, 440, 310, 280, 350, 290,340,420,380,300,290],
            backgroundColor: 'green'
        }]
    },
    options: {
        responsive: true,
        scales: {
            y: {
                beginAtZero: true,
                max: 600,
                ticks: {
                    callback: function(value) {
                        return value + ' M';
                    }
                }
            }
        },
        plugins: {
            tooltip: {
                enabled: true
            }
        }
    }
});
