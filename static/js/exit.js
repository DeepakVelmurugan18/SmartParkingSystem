const socket = io();

const banner = document.getElementById('traffic-banner');
const videoWrapper = document.getElementById('video-wrapper');
const statusEl = document.getElementById('system-status');
const scanner = document.getElementById('scanner-line');

let currentCameraUrl = "";
let lastProcessedPlate = "";

document.addEventListener('DOMContentLoaded', () => {
    fetchStatus();
    fetchCameraInfo();
    setInterval(fetchCameraInfo, 5000); // Poll for updated IP
    
    setTrafficLight('red', '🔴 APPROACH EXIT TO SCAN PLATE', 'Waiting for vehicle...');

    socket.on('stats_update', (data) => {
        // UI update if needed
    });

    // Hardware Socket Listeners
    socket.on('exit_camera_motion_detected', () => {
        setBracketColor('var(--success)');
        document.getElementById('capture-zone-text-inner').textContent = 'Vehicle detected - Capturing...';
        setTrafficLight('green', '🟢 VEHICLE DETECTED', 'Stable. Capturing image...');
    });

    socket.on('exit_camera_capture_started', () => {
        scanner.style.display = 'block';
        scanner.style.animation = 'scanEffect 1.5s linear infinite';
        freezeCameraFrame();
    });

    socket.on('exit_camera_upload_complete', () => {
        setTrafficLight('blue', '🔵 AI PROCESSING', 'Recognizing license plate...');
    });

    socket.on('camera_ocr_result_exit', (data) => {
        if(data.success && data.plate_number !== "NO_PLATE_FOUND") {
            handleOcrSuccess(data);
        } else {
            handleOcrFail(data);
        }
    });
    
    socket.on('exit_success', (data) => {
        if (data.vehicle_id === lastProcessedPlate) {
            document.getElementById('entry-time').textContent = data.entry_time;
            document.getElementById('parking-duration').textContent = data.duration;
            
            setTrafficLight('green', '🟢 CHECKOUT SUCCESSFUL', 'Gate Opening...');
            document.getElementById('action-buttons').style.display = 'none';
            
            // Show success animation
            document.getElementById('success-overlay').style.display = 'flex';
            
            // Auto reset after 5 seconds to prepare for next vehicle
            setTimeout(() => {
                document.getElementById('success-overlay').style.display = 'none';
                resetUI();
            }, 5000);
        }
    });

    // Button Listeners
    document.getElementById('btn-retake').addEventListener('click', () => {
        resetUI();
    });
});

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

function handleOcrSuccess(data) {
    document.getElementById('camera-placeholder').style.display = 'none';
    
    // Show Image in Snapshot Panel
    if(data.image_url) {
        const snap = document.getElementById('captured-snapshot');
        snap.src = data.image_url + '?t=' + Date.now();
        snap.style.display = 'block';
        document.getElementById('snapshot-placeholder').style.display = 'none';
    }

    scanner.style.display = 'none';
    scanner.style.animation = 'none';
    
    let confValue = parseFloat(data.confidence);
    if (confValue <= 1.0) confValue *= 100;

    let displayConf = data.confidence_str || `${confValue.toFixed(1)}%`;
    document.getElementById('ocr-confidence').textContent = displayConf;

    if (confValue < 80) {
        setTrafficLight('yellow', `🟡 LOW CONFIDENCE: ${displayConf}`, `Verify Plate: ${data.plate_number}`);
        document.getElementById('btn-retake').style.display = 'block';
    } else {
        setTrafficLight('blue', `🔵 CONFIDENCE: ${displayConf}`, `Verifying Database...`);
        document.getElementById('btn-retake').style.display = 'none';
    }
    
    lastProcessedPlate = data.plate_number;
    document.getElementById('ocr-plate-number').textContent = lastProcessedPlate;
    
    // Automatically trigger exit sequence
    setTimeout(() => {
        processExit(data.plate_number, data.original_image);
    }, 500);
}

function handleOcrFail(data) {
    scanner.style.display = 'none';
    scanner.style.animation = 'none';
    document.getElementById('camera-placeholder').style.display = 'none';
    
    if(data && data.image_url) {
        const snap = document.getElementById('captured-snapshot');
        snap.src = data.image_url + '?t=' + Date.now();
        snap.style.display = 'block';
        document.getElementById('snapshot-placeholder').style.display = 'none';
    }
    
    setTrafficLight('red', '🔴 OCR Failed', 'Please Retake Scan');
    document.getElementById('ocr-plate-number').textContent = "NO_PLATE_FOUND";
    
    document.getElementById('action-buttons').style.display = 'flex';
    document.getElementById('btn-retake').style.display = 'block';
}

async function processExit(plateNumber, originalImage) {
    try {
        const payload = {
            vehicle_id: plateNumber,
            original_image: originalImage
        };
        
        const res = await fetch('/api/vehicle-exit', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        
        const data = await res.json();
        
        if (!data.success) {
            setTrafficLight('red', '🔴 CHECKOUT FAILED', data.message);
            alert(data.message);
            document.getElementById('action-buttons').style.display = 'flex';
            document.getElementById('btn-retake').style.display = 'block';
        }
        // If success, we wait for the 'exit_success' websocket event to open the gate and show success.
    } catch(e) {
        console.error(e);
        setTrafficLight('red', '🔴 SYSTEM ERROR', 'Please contact admin');
        document.getElementById('action-buttons').style.display = 'flex';
        document.getElementById('btn-retake').style.display = 'block';
    }
}

function resetUI() {
    setTrafficLight('red', '🔴 APPROACH EXIT TO SCAN PLATE', 'Waiting for vehicle...');
    setBracketColor('var(--danger)');
    
    document.getElementById('capture-zone-text-inner').textContent = 'Align Vehicle Plate Here';
    document.getElementById('captured-snapshot').style.display = 'none';
    document.getElementById('snapshot-placeholder').style.display = 'block';
    document.getElementById('ocr-plate-number').textContent = "--------";
    document.getElementById('ocr-confidence').textContent = "--";
    document.getElementById('assigned-slot').textContent = "--";
    document.getElementById('entry-time').textContent = "--";
    document.getElementById('exit-time').textContent = "--";
    document.getElementById('parking-duration').textContent = "--";
    
    document.getElementById('action-buttons').style.display = 'none';
    document.getElementById('btn-retake').style.display = 'none';
    
    unfreezeCameraFrame();
}

async function fetchStatus() {
    try {
        const res = await fetch('/api/gate-status');
        const data = await res.json();
        // Just for initial load, usually socket updates handle the rest
    } catch(e) { console.error(e); }
}

async function fetchCameraInfo() {
    try {
        const res = await fetch('/api/camera/info');
        const data = await res.json();
        const img = document.getElementById('live-camera-feed');
        
        if (data.online && data.stream_url) {
            if (currentCameraUrl !== data.stream_url) {
                currentCameraUrl = data.stream_url;
                img.src = currentCameraUrl;
                img.style.display = 'block';
                document.getElementById('camera-placeholder').style.display = 'none';
            }
        } else {
            img.style.display = 'none';
            document.getElementById('camera-placeholder').style.display = 'block';
            currentCameraUrl = "";
        }
    } catch(e) {
        console.error(e);
    }
}

function freezeCameraFrame() {
    // Cannot natively freeze MJPEG cleanly without canvas tricks.
    // For presentation, we add an overlay.
    document.getElementById('live-camera-feed').style.filter = "brightness(0.5) blur(2px)";
}

function unfreezeCameraFrame() {
    document.getElementById('live-camera-feed').style.filter = "none";
}
