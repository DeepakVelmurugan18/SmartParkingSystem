let currentPaymentId = null;
const socket = io();

document.addEventListener('DOMContentLoaded', () => {
    // Initial fetch to populate UI
    fetchStatus();
    fetchLogs();
    fetchGateStatus();
    
    // Socket.IO Listeners for Real-Time Updates
    socket.on('stats_update', (data) => {
        updateDashboard(data);
    });

    socket.on('gate_update', (data) => {
        updateGateStatusUI(data.gate_status);
    });

    socket.on('logs_update', (data) => {
        updateLogsTable(data.logs);
    });

    // Button Listeners
    document.getElementById('btn-assign-slot').addEventListener('click', assignSlotAndPay);
    document.getElementById('btn-vehicle-entry').addEventListener('click', vehicleEntry);
    document.getElementById('btn-vehicle-exit').addEventListener('click', vehicleExit);
    
    document.getElementById('btn-simulate-payment').addEventListener('click', processPayment);
    document.getElementById('btn-cancel-payment').addEventListener('click', closeModal);
    
    document.getElementById('btn-view-logs').addEventListener('click', () => {
        document.getElementById('logs-modal').style.display = 'block';
    });
    
    document.getElementById('btn-close-logs').addEventListener('click', () => {
        document.getElementById('logs-modal').style.display = 'none';
    });
});

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
        console.error('Error fetching gate status:', error);
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
    document.getElementById('total-slots').textContent = data.total_slots;
    document.getElementById('occupied-slots').textContent = data.occupied;
    document.getElementById('available-slots').textContent = data.available;
    
    document.getElementById('today-entries').textContent = data.today_entries;
    document.getElementById('today-exits').textContent = data.today_exits;
    document.getElementById('revenue-today').textContent = data.revenue_today;
    
    if (document.getElementById('predicted-occupancy')) {
        document.getElementById('predicted-occupancy').textContent = data.predicted_occupancy;
    }
    
    renderGrid(data.slots);
}

function updateGateStatusUI(status) {
    const gateText = document.getElementById('gate-status-text');
    gateText.textContent = status;
    gateText.className = status === "OPEN" ? "status-open" : "status-closed";
}

function updateLogsTable(logs) {
    const tbody = document.getElementById('logs-body');
    tbody.innerHTML = '';
    
    logs.forEach(log => {
        const tr = document.createElement('tr');
        const imgHtml = log.image_url ? `<img src="${log.image_url}" class="log-thumbnail" alt="Vehicle">` : 'No Image';
        tr.innerHTML = `
            <td>${log.vehicle_id}</td>
            <td style="color: #2980b9; font-weight: bold;">${log.plate_number}</td>
            <td>${log.slot}</td>
            <td>${imgHtml}</td>
            <td>${log.entry_time}</td>
            <td>${log.exit_time}</td>
        `;
        tbody.appendChild(tr);
    });
}

function renderGrid(slots) {
    const grid = document.getElementById('parking-grid');
    grid.innerHTML = '';
    
    for (const [slotId, status] of Object.entries(slots)) {
        const slotDiv = document.createElement('div');
        slotDiv.className = `slot ${status.toLowerCase()}`;
        const emoji = status === 'Available' ? '🟩' : '🟥';
        slotDiv.innerHTML = `
            <div>${slotId} ${emoji}</div>
            <div style="font-size: 12px; font-weight: normal; margin-top: 5px;">${status}</div>
        `;
        grid.appendChild(slotDiv);
    }
}

async function assignSlotAndPay() {
    const vehicleId = document.getElementById('assign-vehicle-id').value;
    const resultDiv = document.getElementById('assignment-result');
    
    if (!vehicleId) {
        alert("Please enter a Vehicle ID to assign a slot.");
        return;
    }
    
    resultDiv.textContent = 'Assigning via AI...';
    resultDiv.style.color = '#333';
    
    try {
        const response = await fetch('/api/assign-slot', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ vehicle_id: vehicleId })
        });
        const data = await response.json();
        
        if (data.success) {
            resultDiv.innerHTML = `<strong>${data.message}</strong><br>Status: Pending Payment.`;
            resultDiv.style.color = '#f39c12';
            
            // Set entry form fields
            document.getElementById('entry-vehicle-id').value = vehicleId;
            document.getElementById('entry-slot').value = data.assigned_slot;
            document.getElementById('assign-vehicle-id').value = '';
            
            // Open Payment Modal
            currentPaymentId = data.payment_id;
            openModal(vehicleId, data.assigned_slot, data.payment_id, data.amount);
            
        } else {
            resultDiv.textContent = `Error: ${data.message}`;
            resultDiv.style.color = 'red';
        }
    } catch (error) {
        resultDiv.textContent = 'Error communicating with server.';
        resultDiv.style.color = 'red';
    }
}

function openModal(vehicleId, slot, paymentId, amount) {
    document.getElementById('modal-vehicle-id').textContent = vehicleId;
    document.getElementById('modal-slot-id').textContent = slot;
    
    // Update amount dynamically in modal
    const feeElement = document.querySelector('.payment-details p:nth-child(3)');
    if (feeElement) {
        feeElement.innerHTML = `<strong>Fee:</strong> ₹${amount.toFixed(2)}`;
    }
    const scanTextElement = document.querySelector('.scan-text');
    if (scanTextElement) {
        scanTextElement.textContent = `Scan to pay ₹${amount.toFixed(2)} via UPI`;
    }
    
    document.getElementById('qr-image').src = `/api/generate-qr/${paymentId}`;
    document.getElementById('payment-modal').style.display = 'block';
}

function closeModal() {
    document.getElementById('payment-modal').style.display = 'none';
}

async function processPayment() {
    if (!currentPaymentId) return;
    
    try {
        const response = await fetch('/api/process-payment', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ payment_id: currentPaymentId })
        });
        
        const data = await response.json();
        if (data.success) {
            alert('Payment Successful! Gate is Opening.');
            closeModal();
            document.getElementById('assignment-result').textContent = 'Payment Complete. You may enter.';
            document.getElementById('assignment-result').style.color = 'green';
            
            // Open Gate & Enable Entry
            await fetch('/api/open-gate', { method: 'POST' });
            document.getElementById('btn-vehicle-entry').disabled = false;
        } else {
            alert('Payment Failed: ' + data.message);
        }
    } catch (error) {
        alert('Payment Error.');
    }
}

async function vehicleEntry() {
    const vehicleId = document.getElementById('entry-vehicle-id').value;
    const slot = document.getElementById('entry-slot').value;
    const imageInput = document.getElementById('entry-image');
    
    if (!vehicleId || !slot) {
        alert("Vehicle ID and Slot are missing.");
        return;
    }
    
    const formData = new FormData();
    formData.append('vehicle_id', vehicleId);
    formData.append('slot', slot);
    
    if (imageInput.files.length > 0) {
        formData.append('vehicle_image', imageInput.files[0]);
    }
    
    try {
        const response = await fetch('/api/vehicle-entry', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        if (data.success) {
            alert('Vehicle entered successfully. Gate closing.');
            
            // Reset fields and disable entry
            document.getElementById('entry-vehicle-id').value = '';
            document.getElementById('entry-slot').value = '';
            imageInput.value = ''; 
            document.getElementById('btn-vehicle-entry').disabled = true;
            document.getElementById('assignment-result').textContent = '';
            
            // Close Gate
            await fetch('/api/close-gate', { method: 'POST' });
        } else {
            alert('Error: ' + data.message);
        }
    } catch (error) {
        alert('Error logging vehicle entry.');
    }
}

async function vehicleExit() {
    const vehicleId = document.getElementById('exit-vehicle-id').value;
    
    if (!vehicleId) {
        alert("Please enter Vehicle ID.");
        return;
    }
    
    try {
        // Open gate for exit
        await fetch('/api/open-gate', { method: 'POST' });
        
        const response = await fetch('/api/vehicle-exit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ vehicle_id: vehicleId })
        });
        
        const data = await response.json();
        if (data.success) {
            alert('Vehicle exited successfully! Gate closing.');
            document.getElementById('exit-vehicle-id').value = '';
            
            // Close gate after exit
            await fetch('/api/close-gate', { method: 'POST' });
        } else {
            alert('Error: ' + data.message);
            await fetch('/api/close-gate', { method: 'POST' });
        }
    } catch (error) {
        alert('Error logging vehicle exit.');
    }
}
