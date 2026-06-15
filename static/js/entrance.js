const socket = io();
let currentPaymentId = null;
let assignedSlotId = null;
let enteredVehicleId = null;

let currentVehicleType = "Car";
let currentOriginalImage = null;
let currentBoundedImage = null;
let currentCroppedImage = null;

let currentCameraUrl = "";

const banner = document.getElementById('traffic-banner');
const videoWrapper = document.getElementById('video-wrapper');
const statusEl = document.getElementById('system-status');
const scanner = document.getElementById('scanner-line');

document.addEventListener('DOMContentLoaded', () => {
    fetchStatus();
    fetchCameraInfo();
    setInterval(fetchCameraInfo, 5000); // Poll for updated IP
    
    setTrafficLight('red', '🔴 PLEASE MOVE FORWARD', 'Waiting for vehicle...');

    socket.on('stats_update', (data) => {
        // UI update
    });

    // Hardware Socket Listeners
    socket.on('camera_motion_detected', () => {
        setStep(2);
        setBracketColor('var(--success)');
        document.getElementById('capture-zone-text-inner').textContent = 'Vehicle detected - Capturing...';
        setTrafficLight('green', '🟢 VEHICLE DETECTED', 'Stable. Capturing image...');
    });

    socket.on('camera_capture_started', () => {
        setStep(3);
        scanner.style.display = 'block';
        scanner.style.animation = 'scanEffect 1.5s linear infinite';
        freezeCameraFrame();
    });

    socket.on('camera_upload_complete', () => {
        setStep(4);
        setTrafficLight('blue', '🔵 AI PROCESSING', 'Recognizing license plate...');
    });

    socket.on('camera_ocr_result_entrance', (data) => {
        if(data.success && data.plate_number !== "NO_PLATE_FOUND") {
            handleOcrSuccess(data);
        } else {
            handleOcrFail(data);
        }
    });

    socket.on('payment_success', (data) => {
        if (data.server_timestamp) fetch('/api/log-latency', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({event:'payment_success', latency:Date.now()-data.server_timestamp})});
        if (currentPaymentId == data.payment_id || enteredVehicleId == data.vehicle_id) {
            setTrafficLight('green', '🟢 PAYMENT SUCCESSFUL', 'Gate Opening...');
            document.getElementById('action-buttons').style.display = 'none';
            document.getElementById('qr-container').style.display = 'none';
            
            // Show success animation
            document.getElementById('success-overlay').style.display = 'flex';
            
            // Auto reset after 4 seconds to prepare for next vehicle
            setTimeout(() => {
                document.getElementById('success-overlay').style.display = 'none';
                resetUI();
            }, 4000);
        }
    });

    socket.on('reservation_timeout', (data) => {
        setTrafficLight('red', '🔴 RESERVATION TIMEOUT', 'Payment time expired.');
        document.getElementById('qr-container').style.display = 'none';
        document.getElementById('btn-retake').style.display = 'block';
    });

    // Button Listeners
    document.getElementById('btn-retake').addEventListener('click', () => {
        resetUI();
    });

    document.getElementById('btn-confirm').addEventListener('click', () => {
        document.getElementById('action-buttons').style.display = 'none';
        getSlotAndPay();
    });
    
    // Manual Payment simulation for demo purposes
    document.getElementById('btn-simulate-pay').addEventListener('click', simulatePaymentAndOpenGate);
    
    // Force Capture for testing
    const btnForceCapture = document.getElementById('btn-force-capture');
    if (btnForceCapture) {
        btnForceCapture.addEventListener('click', async () => {
            btnForceCapture.disabled = true;
            btnForceCapture.textContent = "Requesting Capture...";
            try {
                await fetch('/api/camera/request-capture', { method: 'POST' });
                setTimeout(() => {
                    btnForceCapture.disabled = false;
                    btnForceCapture.textContent = "📸 Force Capture";
                }, 3000);
            } catch(e) {
                console.error("Force capture failed", e);
                btnForceCapture.disabled = false;
                btnForceCapture.textContent = "📸 Force Capture";
            }
        });
    }
});

function setStep(stepNum) {
    for(let i=1; i<=5; i++) {
        document.getElementById(`step-${i}`).classList.remove('active');
    }
    document.getElementById(`step-${stepNum}`).classList.add('active');
}

function setBracketColor(color) {
    document.getElementById('bracket-tl').style.borderColor = color;
    document.getElementById('bracket-tr').style.borderColor = color;
    document.getElementById('bracket-bl').style.borderColor = color;
    document.getElementById('bracket-br').style.borderColor = color;
}

function setTrafficLight(color, bannerText, statusText) {
    banner.className = `traffic-light-banner traffic-${color}`;
    banner.textContent = bannerText;
    videoWrapper.className = `video-container camera-border-${color}`;
    statusEl.textContent = `Status: ${statusText}`;
    
    if (color === 'red') statusEl.style.color = 'var(--danger)';
    if (color === 'green') statusEl.style.color = 'var(--success)';
    if (color === 'yellow') statusEl.style.color = 'var(--warning)';
    if (color === 'blue') statusEl.style.color = 'var(--primary)';
}

function triggerArrivalFlow() {
    // Left for backwards compatibility if needed, but handled by new events now
}

function handleOcrSuccess(data) {
    setStep(5);
    
    currentVehicleType = data.vehicle_type || "Car";
    currentOriginalImage = data.original_image;
    currentBoundedImage = data.bounded_image;
    currentCroppedImage = data.cropped_image;

    document.getElementById('camera-placeholder').style.display = 'none';
    
    console.log("Received OCR payload:", data);
    console.log("Image URL:", data.image_url);

    // Duplicate Check
    if (data.is_duplicate) {
        setTrafficLight('blue', '🔵 DUPLICATE SCAN', 'Vehicle already processed. Please proceed.');
        document.getElementById('action-buttons').style.display = 'none';
        
        scanner.style.display = 'none';
        scanner.style.animation = 'none';
        
        setTimeout(() => resetStatusOnly(), 4000);
        return;
    }

    // Show Image in Snapshot Panel
    if(data.image_url) {
        const snap = document.getElementById('captured-snapshot');
        snap.src = data.image_url + '?t=' + Date.now();
        snap.style.display = 'block';
        document.getElementById('snapshot-placeholder').style.display = 'none';
    }

    scanner.style.display = 'none';
    scanner.style.animation = 'none';
    
    // Check confidence
    let confValue = parseFloat(data.confidence);
    // If it's a decimal (e.g., 0.95), convert to percentage
    if (confValue <= 1.0) confValue *= 100;

    let displayConf = data.confidence_str || `${confValue.toFixed(1)}%`;
    document.getElementById('ocr-confidence').textContent = displayConf;

    if (confValue < 80) {
        setTrafficLight('yellow', `🟡 LOW CONFIDENCE: ${displayConf}`, `Verify Plate: ${data.plate_number}`);
        document.getElementById('btn-retake').style.display = 'block';
    } else {
        setTrafficLight('green', `🟢 CONFIDENCE: ${displayConf}`, `AI Recommendation Proceeding...`);
        document.getElementById('btn-retake').style.display = 'none';
    }
    
    enteredVehicleId = data.plate_number;
    document.getElementById('ocr-plate-number').textContent = enteredVehicleId;
    
    document.getElementById('action-buttons').style.display = 'flex';
    document.getElementById('btn-confirm').style.display = 'block';
}

function handleOcrFail(data) {
    setStep(5);
    scanner.style.display = 'none';
    scanner.style.animation = 'none';
    
    document.getElementById('camera-placeholder').style.display = 'none';
    
    console.log("Received OCR payload:", data);
    console.log("Image URL:", data.image_url);
    
    if(data && data.image_url) {
        const snap = document.getElementById('captured-snapshot');
        snap.src = data.image_url + '?t=' + Date.now();
        snap.style.display = 'block';
        document.getElementById('snapshot-placeholder').style.display = 'none';
    }
    
    setTrafficLight('red', '🔴 OCR Failed', 'Please reposition and Retake.');
    
    document.getElementById('ocr-plate-number').textContent = "NO_PLATE_FOUND";
    
    document.getElementById('action-buttons').style.display = 'flex';
    document.getElementById('btn-retake').style.display = 'block';
    document.getElementById('btn-confirm').style.display = 'none';
}

async function getSlotAndPay() {
    try {
        const payload = {
            vehicle_id: enteredVehicleId,
            vehicle_type: currentVehicleType,
            original_image: currentOriginalImage,
            bounded_image: currentBoundedImage,
            cropped_image: currentCroppedImage
        };
        
        const res = await fetch('/api/assign-slot', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        
        if(data.success) {
            assignedSlotId = data.assigned_slot;
            currentPaymentId = data.payment_id;
            
            document.getElementById('assigned-slot').textContent = data.assigned_slot;
            document.getElementById('payment-amount').textContent = data.amount.toFixed(2);
            
            document.getElementById('qr-image').src = `/api/generate-qr/${data.payment_id}`;
            document.getElementById('qr-placeholder').style.display = 'none';
            document.getElementById('qr-container').style.display = 'block';
            
            setTrafficLight('yellow', '🟡 AWAITING PAYMENT', 'Please scan QR code to pay ₹' + data.amount.toFixed(2));
            
            // Note: Simulation timeout removed. System now awaits the 'payment_success' WebSocket event.

        } else {
            if(data.duplicate) {
                alert(`⚠ Vehicle Already Inside Parking\nPlate: ${data.plate_number}\nAssigned Slot: ${data.assigned_slot}`);
            } else {
                alert(data.message);
            }
            resetUI();
        }
    } catch(e) {
        console.error(e);
        resetUI();
    }
}

async function simulatePaymentAndOpenGate() {
    try {
        const res = await fetch('/api/process-payment', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ payment_id: currentPaymentId })
        });
        const data = await res.json();
        
        if(data.success) {
            document.getElementById('step-gate').style.display = 'flex';
            
            // Open gate
            await fetch('/api/open-gate', { method: 'POST' });
            
            // Trigger entry
            const formData = new FormData();
            formData.append('vehicle_id', enteredVehicleId);
            formData.append('slot', assignedSlotId);
            await fetch('/api/vehicle-entry', { method: 'POST', body: formData });
            
            // Close gate and reset status immediately
            await fetch('/api/close-gate', { method: 'POST' });
            resetStatusOnly();
        }
    } catch(e) {
        console.error(e);
    }
}

function resetStatusOnly() {
    document.getElementById('step-gate').style.display = 'none';
    
    // Ensure stream is running
    if (document.getElementById('live-camera-feed').style.display === 'none') {
        startLiveStream();
    }
    
    scanner.style.display = 'none';
    scanner.style.animation = 'none';
    
    document.getElementById('qr-container').style.display = 'none';
    document.getElementById('qr-placeholder').style.display = 'block';
    
    document.getElementById('action-buttons').style.display = 'none';
    
    setStep(1);
    
    setTrafficLight('green', '✅ ENTRY COMPLETED', 'Ready for Next Vehicle');
    
    // We intentionally DO NOT clear the OCR Plate, Slot, Fee, or Captured Snapshot!
    // They will naturally be overwritten by the next capture.
}

function resetUI() {
    document.getElementById('step-gate').style.display = 'none';
    
    // Ensure stream is running
    if (document.getElementById('live-camera-feed').style.display === 'none') {
        startLiveStream();
    }
    
    scanner.style.display = 'none';
    scanner.style.animation = 'none';
    
    document.getElementById('ocr-plate-number').textContent = '--------';
    document.getElementById('assigned-slot').textContent = '--';
    document.getElementById('payment-amount').textContent = '--';
    
    document.getElementById('captured-snapshot').style.display = 'none';
    document.getElementById('captured-snapshot').src = '';
    document.getElementById('snapshot-placeholder').style.display = 'block';
    
    document.getElementById('qr-container').style.display = 'none';
    document.getElementById('qr-placeholder').style.display = 'block';
    
    document.getElementById('action-buttons').style.display = 'none';
    
    setStep(1);
    
    setTrafficLight('red', '🔴 WAITING FOR VEHICLE', 'Waiting for vehicle...');
}

async function fetchCameraInfo() {
    try {
        const res = await fetch('/api/camera/info');
        const data = await res.json();
        if(data.online && data.stream_url) {
            if(currentCameraUrl !== data.stream_url) {
                currentCameraUrl = data.stream_url;
                if(document.getElementById('live-camera-feed').src.indexOf('static/uploads') === -1) {
                    startLiveStream();
                }
            }
        } else {
            if(!currentCameraUrl) {
                document.getElementById('camera-placeholder').textContent = 'ESP32-CAM Offline. Awaiting Registration...';
            }
        }
    } catch(e) {
        console.error("Error fetching camera info:", e);
    }
}

function startLiveStream() {
    const feed = document.getElementById('live-camera-feed');
    
    if(currentCameraUrl) {
        feed.src = currentCameraUrl;
        feed.style.display = 'block';
        document.getElementById('camera-placeholder').style.display = 'none';
    } else {
        feed.style.display = 'none';
        document.getElementById('camera-placeholder').style.display = 'block';
    }
}

async function fetchStatus() {
    // Keep alive function
}
