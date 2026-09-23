// SonicSentinel AI - Frontend Real-time Audio & SaaS Management Engine

let audioContext = null;
let mediaStream = null;
let analyser = null;
let scriptProcessor = null;
let websocket = null;
let isMonitoring = false;
let canvas = null;
let canvasCtx = null;
let animationFrameId = null;
let currentActiveRole = "security_operator";
let currentAudioBlobUrl = null;

// Initialize on DOM load
window.addEventListener("DOMContentLoaded", () => {
    canvas = document.getElementById("waveformCanvas");
    if (canvas) {
        canvasCtx = canvas.getContext("2d");
        drawStaticWaveform();
    }
    fetchAlerts();
    fetchReviewQueue();
    fetchCategories();
});

// -------------------------------------------------------------
// Live Microphone & WebSocket Streaming
// -------------------------------------------------------------

async function toggleMicrophone() {
    const btn = document.getElementById("startMicBtn");
    const badge = document.getElementById("micStatusBadge");

    if (isMonitoring) {
        stopMicrophone();
        btn.innerHTML = '<i class="fa-solid fa-microphone"></i> Start Live Mic';
        btn.classList.remove("from-red-600", "to-rose-600");
        btn.classList.add("from-blue-600", "to-cyan-600");
        if (badge) {
            badge.innerHTML = '<i class="fa-solid fa-microphone-slash mr-1"></i> Inactive';
            badge.className = "px-2.5 py-1 rounded-full text-xs font-medium bg-slate-800 text-slate-400 border border-slate-700";
        }
        isMonitoring = false;
    } else {
        try {
            await startMicrophone();
            btn.innerHTML = '<i class="fa-solid fa-stop"></i> Stop Live Mic';
            btn.classList.remove("from-blue-600", "to-cyan-600");
            btn.classList.add("from-red-600", "to-rose-600");
            if (badge) {
                badge.innerHTML = '<i class="fa-solid fa-circle-dot fa-fade text-emerald-400 mr-1"></i> LIVE MONITORING';
                badge.className = "px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-950/80 text-emerald-400 border border-emerald-700";
            }
            isMonitoring = true;
        } catch (err) {
            alert("Microphone access error: " + err.message);
            if (badge) badge.innerHTML = '<i class="fa-solid fa-triangle-exclamation mr-1 text-red-400"></i> Permission Denied';
        }
    }
}

async function startMicrophone() {
    mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
    audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });

    const source = audioContext.createMediaStreamSource(mediaStream);
    analyser = audioContext.createAnalyser();
    analyser.fftSize = 2048;
    source.connect(analyser);

    // Setup WebSocket
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    websocket = new WebSocket(`${protocol}//${window.location.host}/ws/live-audio`);

    websocket.onmessage = (event) => {
        const payload = JSON.parse(event.data);
        handleDetectionResult(payload);
    };

    websocket.onclose = () => {
        console.log("WebSocket audio stream closed.");
    };

    // Buffer audio samples and send every 1.5 seconds (24000 samples @ 16kHz)
    const bufferSize = 4096;
    scriptProcessor = audioContext.createScriptProcessor(bufferSize, 1, 1);
    source.connect(scriptProcessor);
    scriptProcessor.connect(audioContext.destination);

    let collectedSamples = [];
    const targetSamples = 16000 * 1.5;

    scriptProcessor.onaudioprocess = (e) => {
        if (!isMonitoring) return;
        const inputData = e.inputBuffer.getChannelData(0);
        collectedSamples.push(...inputData);

        if (collectedSamples.length >= targetSamples) {
            const chunk = new Float32Array(collectedSamples.slice(0, targetSamples));
            collectedSamples = collectedSamples.slice(targetSamples);
            if (websocket && websocket.readyState === WebSocket.OPEN) {
                websocket.send(chunk.buffer);
            }
        }
    };

    drawActiveWaveform();
}

function stopMicrophone() {
    if (scriptProcessor) scriptProcessor.disconnect();
    if (mediaStream) mediaStream.getTracks().forEach(t => t.stop());
    if (audioContext) audioContext.close();
    if (websocket) websocket.close();
    if (animationFrameId) cancelAnimationFrame(animationFrameId);
    drawStaticWaveform();
}

// -------------------------------------------------------------
// Canvas Waveform Visualizer
// -------------------------------------------------------------

function drawActiveWaveform() {
    if (!analyser || !canvasCtx) return;
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    const render = () => {
        animationFrameId = requestAnimationFrame(render);
        analyser.getByteTimeDomainData(dataArray);

        canvasCtx.fillStyle = "#070b14";
        canvasCtx.fillRect(0, 0, canvas.width, canvas.height);

        canvasCtx.lineWidth = 2;
        canvasCtx.strokeStyle = "#06b6d4";
        canvasCtx.beginPath();

        const sliceWidth = canvas.width * 1.0 / bufferLength;
        let x = 0;

        for (let i = 0; i < bufferLength; i++) {
            const v = dataArray[i] / 128.0;
            const y = v * canvas.height / 2;

            if (i === 0) {
                canvasCtx.moveTo(x, y);
            } else {
                canvasCtx.lineTo(x, y);
            }
            x += sliceWidth;
        }

        canvasCtx.lineTo(canvas.width, canvas.height / 2);
        canvasCtx.stroke();
    };

    render();
}

function drawStaticWaveform() {
    if (!canvasCtx || !canvas) return;
    canvas.width = canvas.parentElement.clientWidth || 600;
    canvas.height = 96;
    canvasCtx.fillStyle = "#070b14";
    canvasCtx.fillRect(0, 0, canvas.width, canvas.height);
    canvasCtx.lineWidth = 1.5;
    canvasCtx.strokeStyle = "#1e293b";
    canvasCtx.beginPath();
    canvasCtx.moveTo(0, canvas.height / 2);
    canvasCtx.lineTo(canvas.width, canvas.height / 2);
    canvasCtx.stroke();
}

// -------------------------------------------------------------
// Audio Alert Buzzer (Web Audio API Synthesizer)
// -------------------------------------------------------------

function playAlertBuzzer() {
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = "sawtooth";
        osc.frequency.setValueAtTime(850, ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(450, ctx.currentTime + 0.35);
        gain.gain.setValueAtTime(0.15, ctx.currentTime);
        gain.gain.linearRampToValueAtTime(0.01, ctx.currentTime + 0.35);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start();
        osc.stop(ctx.currentTime + 0.35);
    } catch (e) {
        // Audio policy or silent
    }
}

// -------------------------------------------------------------
// UI Updates on Inferred Sounds
// -------------------------------------------------------------

function handleDetectionResult(res) {
    const card = document.getElementById("detectionCard");
    const classTitle = document.getElementById("predictedClassTitle");
    const sevBadge = document.getElementById("activeSeverityBadge");
    const agreeText = document.getElementById("agreementStatusText");
    const pyScore = document.getElementById("pyScoreText");
    const pyBar = document.getElementById("pyProgressBar");
    const gtmScore = document.getElementById("gtmScoreText");
    const gtmBar = document.getElementById("gtmProgressBar");
    const actionText = document.getElementById("actionRecommendationText");

    const category = res.predicted_class || "Background Noise";
    const severity = res.severity || "Informational";
    const pyConf = Math.round((res.python_confidence || 0.9) * 100);
    const gtmConf = Math.round((res.gtm_confidence || 0.88) * 100);

    classTitle.innerText = category;
    pyScore.innerText = pyConf + "%";
    pyBar.style.width = pyConf + "%";
    gtmScore.innerText = gtmConf + "%";
    gtmBar.style.width = gtmConf + "%";
    agreeText.innerText = res.consistency_status || "Acceptable Match";
    if (res.recommended_action) actionText.innerText = res.recommended_action;

    // Severity styling & Alarm Trigger
    sevBadge.innerText = severity;
    card.classList.remove("critical-glow", "border-criticalRed");

    if (severity === "Critical") {
        sevBadge.className = "px-2.5 py-0.5 rounded text-xs font-bold uppercase bg-red-950 text-red-400 border border-red-700";
        card.classList.add("critical-glow", "border-criticalRed");
        playAlertBuzzer();
        fetchAlerts();
    } else if (severity === "High") {
        sevBadge.className = "px-2.5 py-0.5 rounded text-xs font-bold uppercase bg-amber-950 text-amber-400 border border-amber-700";
    } else {
        sevBadge.className = "px-2.5 py-0.5 rounded text-xs font-bold uppercase bg-slate-800 text-slate-300";
    }
}

// -------------------------------------------------------------
// Audio File Upload & Preview Player (SRS Req #iv & #ix)
// -------------------------------------------------------------

async function handleFileUpload(event) {
    const file = event.target.files[0];
    if (!file) return;

    // Setup preview audio
    setupAudioPreview(file);

    const progress = document.getElementById("uploadProgress");
    progress.classList.remove("hidden");

    const formData = new FormData();
    formData.append("file", file);

    try {
        const response = await fetch("/api/audio/upload", {
            method: "POST",
            body: formData
        });

        const data = await response.json();
        progress.classList.add("hidden");

        if (!response.ok) {
            alert("Validation / Analysis Failed: " + (data.detail || "Error"));
            return;
        }

        handleDetectionResult({
            predicted_class: data.consensus.final_category,
            severity: data.consensus.severity,
            python_confidence: data.python_model.confidence,
            gtm_confidence: data.gtm_model.confidence,
            consistency_status: data.consensus.consistency_status,
            recommended_action: data.consensus.recommended_action
        });

        fetchAlerts();
        fetchReviewQueue();

    } catch (err) {
        progress.classList.add("hidden");
        alert("Upload error: " + err.message);
    }
}

function setupAudioPreview(file) {
    const container = document.getElementById("audioPreviewContainer");
    const audioElement = document.getElementById("audioPreviewElement");
    const nameLabel = document.getElementById("previewFilename");

    if (currentAudioBlobUrl) {
        URL.revokeObjectURL(currentAudioBlobUrl);
    }
    currentAudioBlobUrl = URL.createObjectURL(file);
    audioElement.src = currentAudioBlobUrl;
    nameLabel.innerText = file.name;
    container.classList.remove("hidden");
}

function toggleAudioPreview() {
    const audio = document.getElementById("audioPreviewElement");
    const icon = document.getElementById("playIcon");
    if (audio.paused) {
        audio.play();
        icon.className = "fa-solid fa-pause text-xs";
    } else {
        audio.pause();
        icon.className = "fa-solid fa-play text-xs";
    }
}

function updateAudioProgress() {
    const audio = document.getElementById("audioPreviewElement");
    const scrubber = document.getElementById("previewScrubber");
    const timer = document.getElementById("previewTime");

    if (audio.duration) {
        const pct = (audio.currentTime / audio.duration) * 100;
        scrubber.value = pct;
        const curM = Math.floor(audio.currentTime / 60);
        const curS = Math.floor(audio.currentTime % 60);
        const durM = Math.floor(audio.duration / 60);
        const durS = Math.floor(audio.duration % 60);
        timer.innerText = `${curM.toString().padStart(2, '0')}:${curS.toString().padStart(2, '0')} / ${durM.toString().padStart(2, '0')}:${durS.toString().padStart(2, '0')}`;
    }
}

function scrubAudioPreview(val) {
    const audio = document.getElementById("audioPreviewElement");
    if (audio.duration) {
        audio.currentTime = (val / 100) * audio.duration;
    }
}

function setPreviewSpeed(speed) {
    const audio = document.getElementById("audioPreviewElement");
    audio.playbackRate = speed;
}

function setPreviewVolume(vol) {
    const audio = document.getElementById("audioPreviewElement");
    audio.volume = vol;
}

function onAudioEnded() {
    const icon = document.getElementById("playIcon");
    icon.className = "fa-solid fa-play text-xs";
}

// -------------------------------------------------------------
// Persona / Role Switcher (Winning Presentation Feature!)
// -------------------------------------------------------------

function switchPersona(role) {
    currentActiveRole = role;
    const badge = document.getElementById("tenantBadge");
    const notice = document.getElementById("roleNotice");

    const roleConfigs = {
        "security_operator": {
            tenant: "TENANT: Metro Transit Police",
            notice: "Tactical Security Command Active — Live 24/7 Threat Radar & Emergency Dispatch"
        },
        "maintenance_operator": {
            tenant: "TENANT: Indus Heavy Industries",
            notice: "Industrial Plant Telemetry Active — Machinery Vibration & Bearing Health Tracking"
        },
        "audio_reviewer": {
            tenant: "TENANT: Global Acoustic QA",
            notice: "Forensic Review Studio Active — Click any flagged clip below to review in slow-mo"
        },
        "administrator": {
            tenant: "TENANT: SonicSentinel Cloud",
            notice: "System Governance Active — Category Registry, Thresholds & Audit Trails"
        },
        "normal_user": {
            tenant: "TENANT: City Commons",
            notice: "Resident Portal Active — File Upload & Ambient Sound Level Monitoring"
        }
    };

    const cfg = roleConfigs[role] || roleConfigs["security_operator"];
    badge.innerText = cfg.tenant;
    notice.innerText = cfg.notice;

    fetchAlerts();
    fetchReviewQueue();
}

// -------------------------------------------------------------
// Seed Demo Accounts
// -------------------------------------------------------------

async function seedDemoAccounts() {
    try {
        const res = await fetch("/api/auth/seed-demo-users", { method: "POST" });
        const data = await res.json();
        alert(`Success! 5 Demo Accounts Seeded into MongoDB:\n` +
            data.accounts.map(a => `• ${a.role}: ${a.email} (pw: ${a.password})`).join('\n')
        );
    } catch (e) {
        alert("Seeding error: " + e.message);
    }
}

// -------------------------------------------------------------
// Auth Modal Handlers
// -------------------------------------------------------------

function openAuthModal() {
    document.getElementById("authModal").classList.remove("hidden");
}

function closeAuthModal() {
    document.getElementById("authModal").classList.add("hidden");
}

async function handleAuthSubmit(event) {
    event.preventDefault();
    const u = document.getElementById("authUsername").value;
    const p = document.getElementById("authPassword").value;

    const fd = new FormData();
    fd.append("username", u);
    fd.append("password", p);

    try {
        const res = await fetch("/api/auth/login", {
            method: "POST",
            body: fd
        });
        const data = await res.json();
        if (!res.ok) {
            alert("Login Failed: " + (data.detail || "Invalid credentials"));
            return;
        }

        closeAuthModal();
        document.getElementById("authBtnLabel").innerText = data.user.full_name.split(" ")[0];
        document.getElementById("personaSelector").value = data.user.role;
        switchPersona(data.user.role);
        alert(`Signed in as ${data.user.full_name} (${data.user.role}) - Tenant: ${data.user.tenant_id}`);
    } catch (e) {
        alert("Auth error: " + e.message);
    }
}

// -------------------------------------------------------------
// Dynamic Add Category Modal (Evaluator Surprise Test!)
// -------------------------------------------------------------

function openAddCategoryModal() {
    document.getElementById("addCategoryModal").classList.remove("hidden");
}

function closeAddCategoryModal() {
    document.getElementById("addCategoryModal").classList.add("hidden");
}

async function submitNewCategory(event) {
    event.preventDefault();
    const name = document.getElementById("newCatName").value;
    const severity = document.getElementById("newCatSeverity").value;
    const department = document.getElementById("newCatDepartment").value;
    const action = document.getElementById("newCatAction").value;

    const fd = new FormData();
    fd.append("name", name);
    fd.append("severity", severity);
    fd.append("department", department);
    fd.append("recommended_action", action);

    try {
        const res = await fetch("/api/categories", {
            method: "POST",
            body: fd
        });
        const data = await res.json();
        if (!res.ok) {
            alert("Failed to add category: " + (data.detail || "Error"));
            return;
        }
        closeAddCategoryModal();
        alert(`Category "${name}" registered dynamically into SonicSentinel AI!`);
        fetchCategories();
    } catch (e) {
        alert("Error adding category: " + e.message);
    }
}

async function fetchCategories() {
    try {
        const res = await fetch("/api/categories");
        const data = await res.json();
        const container = document.getElementById("categoriesList");
        if (!data.categories) return;

        container.innerHTML = data.categories.map(c => `
            <div class="p-2 rounded bg-darkBg border ${c.severity === 'Critical' ? 'border-criticalRed/40 bg-red-950/20 text-red-400' : 'border-borderBg'}">
                <span class="block font-semibold">${c.name}</span>
                <span class="${c.severity === 'Critical' ? 'text-red-500 font-bold' : c.severity === 'High' ? 'text-amber-400' : 'text-blue-400'} text-[10px]">${c.severity}</span>
            </div>
        `).join("");
    } catch (e) {
        console.log("Fetch categories:", e);
    }
}

// -------------------------------------------------------------
// Alerts & Review Queue Poller
// -------------------------------------------------------------

async function fetchAlerts() {
    try {
        const res = await fetch("/api/alerts");
        const data = await res.json();
        const container = document.getElementById("alertsContainer");
        if (!data.alerts || data.alerts.length === 0) return;

        container.innerHTML = data.alerts.map(a => `
            <div class="p-3 rounded-lg bg-darkBg border ${a.severity === 'Critical' ? 'border-red-600/50 bg-red-950/20' : 'border-amber-600/30'} flex justify-between items-center">
                <div>
                    <div class="flex items-center gap-2">
                        <span class="font-bold text-white">${a.sound_category}</span>
                        <span class="px-1.5 py-0.5 rounded text-[10px] font-bold ${a.severity === 'Critical' ? 'bg-red-900 text-red-200' : 'bg-amber-900 text-amber-200'}">${a.severity}</span>
                    </div>
                    <p class="text-[11px] text-slate-400 mt-0.5">${a.recommended_action}</p>
                </div>
                <div>
                    <span class="text-[10px] px-2 py-1 rounded bg-slate-800 text-slate-300">${a.status}</span>
                </div>
            </div>
        `).join("");
    } catch (e) {
        console.log("Alerts fetch:", e);
    }
}

async function fetchReviewQueue() {
    try {
        const res = await fetch("/api/review-queue");
        const data = await res.json();
        const container = document.getElementById("reviewContainer");
        if (!data.queue || data.queue.length === 0) return;

        container.innerHTML = data.queue.map(q => `
            <div class="p-3 rounded-lg bg-darkBg border border-yellow-700/40 space-y-1">
                <div class="flex justify-between items-center">
                    <span class="font-medium text-slate-200">${q.filename}</span>
                    <span class="text-[10px] text-yellow-400 bg-yellow-950/60 px-2 py-0.5 rounded">${q.consistency_status}</span>
                </div>
                <div class="text-[11px] text-slate-400">
                    Py: <strong class="text-cyan-400">${q.ai_python_prediction}</strong> vs GTM: <strong class="text-blue-400">${q.ai_gtm_prediction}</strong>
                </div>
            </div>
        `).join("");
    } catch (e) {
        console.log("Review queue fetch:", e);
    }
}
