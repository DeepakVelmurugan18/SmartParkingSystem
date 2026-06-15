const socket = io();

let occupancyChart;

document.addEventListener('DOMContentLoaded', () => {
    initChart();
    fetchStatus();
    fetchLogs();
    fetchGateStatus();
    fetchGateStatus();
    
    socket.on('live_stream_entrance', (data) => {
        const cam = document.getElementById('admin-entrance-cam');
        document.getElementById('admin-entrance-placeholder').style.display = 'none';
        cam.src = 'data:image/jpeg;base64,' + data.image;
        cam.style.display = 'block';
    });

    socket.on('live_stream_exit', (data) => {
        const cam = document.getElementById('admin-exit-cam');
        document.getElementById('admin-exit-placeholder').style.display = 'none';
        cam.src = 'data:image/jpeg;base64,' + data.image;
        cam.style.display = 'block';
    });
    
    socket.on('stats_update', (data) => {
        updateDashboard(data);
    });

    socket.on('gate_update', (data) => {
        updateGateStatusUI(data.gate_status);
        addActivity('Gate Update', `Gate is now ${data.gate_status}`, data.gate_status === 'OPEN' ? 'success' : 'exit');
    });

    socket.on('logs_update', (data) => {
        updateLogsTable(data.logs);
        if(data.logs.length > 0) {
            const latest = data.logs[0];
            addActivity('Vehicle Log', `Plate ${latest.plate_number} | Slot ${latest.slot} | ${latest.payment_status}`, 'entry');
        }
    });

    document.getElementById('btn-open-gate').addEventListener('click', async () => {
        await fetch('/api/open-gate', { method: 'POST' });
    });

    document.getElementById('btn-close-gate').addEventListener('click', async () => {
        await fetch('/api/close-gate', { method: 'POST' });
    });

    // Hardware Simulators
    const btnArrive = document.getElementById('btn-demo-arrive');
    if(btnArrive) btnArrive.addEventListener('click', async () => await fetch('/api/demo/arrive', { method: 'POST' }));
    
    const btnCapture = document.getElementById('btn-demo-capture');
    if(btnCapture) btnCapture.addEventListener('click', async () => await fetch('/api/demo/capture', { method: 'POST' }));
    
    const btnOcr = document.getElementById('btn-demo-ocr');
    if(btnOcr) btnOcr.addEventListener('click', async () => await fetch('/api/demo/ocr', { method: 'POST' }));

    const simUltrasonic = document.getElementById('sim-ultrasonic');
    if(simUltrasonic) simUltrasonic.addEventListener('click', async () => await fetch('/api/simulate/ultrasonic', { method: 'POST' }));
    
    document.getElementById('sim-camera-success').addEventListener('click', async () => {
        await fetch('/api/simulate/camera', { 
            method: 'POST', 
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({status: 'success'}) 
        });
    });

    document.getElementById('sim-camera-fail').addEventListener('click', async () => {
        await fetch('/api/simulate/camera', { 
            method: 'POST', 
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({status: 'fail'}) 
        });
    });

    // Log Search Filter
    document.getElementById('search-logs').addEventListener('input', (e) => {
        const term = e.target.value.toLowerCase();
        const rows = document.querySelectorAll('#logs-body tr');
        rows.forEach(row => {
            const text = row.textContent.toLowerCase();
            row.style.display = text.includes(term) ? '' : 'none';
        });
    });
});

function initChart() {
    const ctx = document.getElementById('occupancyChart').getContext('2d');
    occupancyChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: ['9AM', '10AM', '11AM', '12PM', '1PM', '2PM', '3PM'],
            datasets: [{
                label: 'Occupied Slots',
                data: [0, 1, 2, 3, 2, 1, 3],
                borderColor: '#00e5ff',
                backgroundColor: 'rgba(0, 229, 255, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: { beginAtZero: true, max: 10, ticks: { color: '#90caf9' }, grid: { color: 'rgba(144, 202, 249, 0.1)' } },
                x: { ticks: { color: '#90caf9' }, grid: { display: false } }
            }
        }
    });
}

async function fetchStatus() {
    try {
        const response = await fetch('/api/dashboard-stats');
        const data = await response.json();
        updateDashboard(data);
    } catch (error) {
        console.error('Error fetching stats:', error);
    }
}

async function fetchGateStatus() {
    try {
        const response = await fetch('/api/gate-status');
        const data = await response.json();
        updateGateStatusUI(data.gate_status);
    } catch (error) {
        console.error('Error fetching gate:', error);
    }
}

async function fetchLogs() {
    try {
        const response = await fetch('/api/logs');
        const data = await response.json();
        updateLogsTable(data.logs);
    } catch (error) {
        console.error('Error fetching logs:', error);
    }
}

function updateDashboard(data) {
    document.getElementById('kpi-total').innerHTML = `${data.total_slots} <span class="kpi-sub">SLOTS</span>`;
    document.getElementById('kpi-occupied').innerHTML = `${data.occupied} <span class="kpi-sub">CARS</span>`;
    document.getElementById('kpi-revenue').textContent = data.revenue_today.toFixed(2);
    
    // Hardcoded demo value for accuracy, or calculate if data provides it
    document.getElementById('kpi-ai-accuracy').innerHTML = `96.5% <span class="kpi-sub">OCR</span>`;

    document.getElementById('ai-occupancy-val').textContent = data.predicted_occupancy;
    
    // Hardware IR Updates based on Slots
    if(data.slots['A1']) document.getElementById('hw-a1').textContent = data.slots['A1'] === 'Occupied' ? 'DETECTED' : 'Idle';
    if(data.slots['A2']) document.getElementById('hw-a2').textContent = data.slots['A2'] === 'Occupied' ? 'DETECTED' : 'Idle';
    if(data.slots['A3']) document.getElementById('hw-a3').textContent = data.slots['A3'] === 'Occupied' ? 'DETECTED' : 'Idle';
    
    document.getElementById('hw-a1').style.color = data.slots['A1'] === 'Occupied' ? 'var(--danger)' : 'var(--text-secondary)';
    document.getElementById('hw-a2').style.color = data.slots['A2'] === 'Occupied' ? 'var(--danger)' : 'var(--text-secondary)';
    document.getElementById('hw-a3').style.color = data.slots['A3'] === 'Occupied' ? 'var(--danger)' : 'var(--text-secondary)';

    renderGrid(data.slots);
    
    // Randomly update chart last point for live effect
    if(occupancyChart) {
        const dataArr = occupancyChart.data.datasets[0].data;
        dataArr[dataArr.length - 1] = data.occupied;
        occupancyChart.update();
    }
}

function renderGrid(slots) {
    const grid = document.getElementById('main-parking-grid');
    grid.innerHTML = '';
    
    const slotKeys = Object.keys(slots).sort();
    slotKeys.forEach(slotId => {
        const status = slots[slotId];
        const isFree = status === 'Available';
        const nodeClass = isFree ? 'free' : 'occupied';
        
        const slotHtml = `
            <div class="slot-node ${nodeClass}" onclick="toggleSlot('${slotId}', '${isFree ? 'Occupied' : 'Available'}')">
                <div class="slot-id">${slotId}</div>
                <div class="slot-status">${status}</div>
                <div class="tooltip">
                    <strong>${slotId} Details</strong><br>
                    Status: ${status}<br>
                    Sensor: ${isFree ? 'Clear' : 'Blocked'}
                </div>
            </div>
        `;
        grid.insertAdjacentHTML('beforeend', slotHtml);
    });
}

async function toggleSlot(slotId, newStatus) {
    await fetch('/api/hardware/update-slot', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({slot_id: slotId, status: newStatus})
    });
}

function updateGateStatusUI(status) {
    const hwGate = document.getElementById('hw-gate-status');
    hwGate.textContent = status;
    hwGate.style.color = status === "OPEN" ? "var(--success)" : "var(--danger)";
}

function updateLogsTable(logs) {
    const tbody = document.getElementById('logs-body');
    tbody.innerHTML = '';
    
    logs.forEach(log => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><span class="plate-badge">${log.plate_number}</span></td>
            <td style="font-weight:bold; color:#fff;">${log.slot}</td>
            <td>${log.entry_time.split(' ')[1] || log.entry_time}</td>
            <td>${log.exit_time !== '-' ? log.exit_time.split(' ')[1] : '-'}</td>
            <td><span style="color: ${log.payment_status === 'Paid' ? 'var(--success)' : 'var(--warning)'}">${log.payment_status}</span></td>
            <td>₹${log.amount.toFixed(2)}</td>
            <td>${log.status}</td>
        `;
        tbody.appendChild(tr);
    });
}

function addActivity(title, desc, typeClass) {
    const feed = document.getElementById('activity-feed');
    const time = new Date().toLocaleTimeString();
    const item = `
        <div class="activity-item ${typeClass}">
            <span class="act-time">${time} - ${title}</span>
            <span class="act-desc">${desc}</span>
        </div>
    `;
    feed.insertAdjacentHTML('afterbegin', item);
}


