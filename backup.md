<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mewar Hi-Tech | Anti-Gravity Twin</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Oswald:wght@500;600;700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500;600&display=swap');

        /* Default (Night Mode) Variables */
        :root {
            --bg-gradient: radial-gradient(circle at center, #0a1118 0%, #030508 100%);
            --panel-bg: rgba(10, 14, 20, 0.98);
            --panel-border: rgba(0, 240, 255, 0.3);
            --text-main: #ffffff;
            --text-muted: #8892a0;
            --accent-cyan: #00F0FF;
            --accent-yellow: #FFC72C;
            --accent-green: #3DDC84;
            --log-bg: rgba(255, 255, 255, 0.05);
            --grid-color: rgba(0, 240, 255, 0.04);
        }

        /* Day Mode Variables */
        body.day-mode {
            --bg-gradient: radial-gradient(circle at center, #e2e8f0 0%, #94a3b8 100%);
            --panel-bg: rgba(255, 255, 255, 0.95);
            --panel-border: rgba(15, 23, 42, 0.2);
            --text-main: #0f172a;
            --text-muted: #475569;
            --accent-cyan: #0284c7; /* Darker blue for day */
            --accent-yellow: #d97706; /* Darker amber for day */
            --accent-green: #16a34a;
            --log-bg: rgba(0, 0, 0, 0.04);
            --grid-color: rgba(15, 23, 42, 0.04);
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            width: 100%; height: 100vh; overflow: hidden;
            background: var(--bg-gradient);
            font-family: 'Inter', sans-serif;
            color: var(--text-main);
            transition: background 1s ease;
        }

        #canvas-container { position: absolute; inset: 0; width: 100%; height: 100%; }
        canvas { display: block; }

        #grid-overlay {
            position: absolute; inset: 0; pointer-events: none; z-index: 4;
            background-image: 
                linear-gradient(var(--grid-color) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-color) 1px, transparent 1px);
            background-size: 40px 40px;
            transition: all 1s ease;
        }

        /* Top Left Controls */
        .controls-wrapper {
            position: absolute; top: 24px; left: 28px; z-index: 20;
            display: flex; gap: 12px;
        }

        .btn-control {
            background: var(--panel-bg);
            border: 1px solid var(--panel-border);
            color: var(--text-main);
            padding: 10px 16px;
            border-radius: 6px;
            font-size: 12px; font-weight: 600; cursor: pointer;
            display: flex; align-items: center; gap: 8px;
            font-family: 'JetBrains Mono', monospace; text-transform: uppercase;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            transition: all 0.3s ease;
        }

        .btn-control:hover { border-color: var(--accent-cyan); transform: translateY(-2px); }

        /* UI Panel (Made clearer and more solid) */
        #ui-layer {
            position: absolute; top: 0; right: 0; width: 100%; height: 100%;
            pointer-events: none; display: flex; flex-direction: column;
            justify-content: space-between; padding: 30px; z-index: 10;
        }

        .panel {
            width: 400px; max-height: calc(100vh - 60px);
            display: flex; flex-direction: column;
            background: var(--panel-bg);
            border: 2px solid var(--panel-border);
            border-radius: 12px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.3);
            pointer-events: auto; overflow: hidden;
            transition: all 0.5s ease;
        }

        .panel-header { background: linear-gradient(90deg, var(--accent-cyan) 0%, var(--accent-yellow) 100%); height: 6px; }

        .brand-block { padding: 24px; border-bottom: 1px solid var(--panel-border); }
        h1 { font-family: 'Oswald', sans-serif; font-size: 26px; margin: 0 0 4px; text-transform: uppercase; color: var(--text-main); }
        .brand-tag { font-family: 'JetBrains Mono', monospace; font-size: 11px; color: var(--accent-cyan); text-transform: uppercase; font-weight: 600;}

        .status-strip { display: flex; gap: 10px; padding: 16px 24px; border-bottom: 1px solid var(--panel-border); }
        .status-chip {
            flex: 1; background: var(--log-bg); border: 1px solid var(--panel-border);
            border-radius: 6px; padding: 12px;
        }
        .status-chip .label { font-family: 'JetBrains Mono', monospace; font-size: 10px; color: var(--text-muted); text-transform: uppercase; margin-bottom: 6px; font-weight: 600;}
        .status-chip .value { font-family: 'Oswald', sans-serif; font-size: 18px; font-weight: 600; display: flex; align-items: center; gap: 8px; color: var(--text-main); }
        
        .dot { width: 10px; height: 10px; border-radius: 50%; background: var(--accent-green); animation: pulse 2s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }

        .log-feed-wrap { flex: 1; overflow-y: auto; padding: 20px 24px; }
        .log-feed-wrap::-webkit-scrollbar { width: 6px; }
        .log-feed-wrap::-webkit-scrollbar-thumb { background: var(--panel-border); border-radius: 3px; }

        .feed-title { font-family: 'JetBrains Mono', monospace; font-size: 11px; color: var(--text-muted); text-transform: uppercase; margin-bottom: 15px; font-weight: 600;}
        
        /* Log Boxes (Crisp and readable) */
        .log-box {
            background: var(--log-bg); border: 1px solid var(--panel-border);
            border-left: 4px solid var(--accent-cyan); padding: 14px; margin-bottom: 12px;
            border-radius: 0 8px 8px 0;
            animation: slideIn 0.3s ease-out forwards;
        }
        @keyframes slideIn { from { transform: translateX(20px); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
        
        .log-time { font-family: 'JetBrains Mono', monospace; color: var(--text-muted); font-size: 10px; font-weight: 600; display: flex; justify-content: space-between; margin-bottom: 8px; }
        .log-task { font-weight: 700; font-size: 14px; color: var(--text-main); margin-bottom: 6px; }
        .log-msg { font-size: 13px; color: var(--text-muted); line-height: 1.5; font-weight: 500;}

        #nameplate { position: absolute; bottom: 30px; left: 30px; pointer-events: none; z-index: 8; }
        #nameplate .name { font-size: 50px; font-weight: 700; color: var(--text-main); text-transform: uppercase; line-height: 0.9; font-family: 'Oswald', sans-serif; transition: color 0.5s ease;}
        #nameplate .name em { color: var(--accent-yellow); font-style: normal; display: block; }
    </style>
</head>
<body>
    <div id="grid-overlay"></div>
    <div id="canvas-container"></div>

    <div class="controls-wrapper">
        <button class="btn-control" id="theme-toggle">
            <span>DAY/NIGHT</span>
        </button>
        <button class="btn-control" id="sound-toggle">
            <span>AUDIO: OFF</span>
        </button>
    </div>

    <div id="nameplate">
        <div class="name">ANTI-GRAVITY<br><em>MODULE</em></div>
    </div>

    <div id="ui-layer">
        <div class="panel">
            <div class="panel-header"></div>
            <div class="brand-block">
                <h1>Mewar Hi-Tech</h1>
                <div class="brand-tag">Exploded View Engine</div>
            </div>
            <div class="status-strip">
                <div class="status-chip">
                    <div class="label">System</div>
                    <div class="value"><span class="dot"></span>Online</div>
                </div>
                <div class="status-chip">
                    <div class="label">Parts Tracked</div>
                    <div class="value" style="color: var(--accent-yellow);">42 Units</div>
                </div>
            </div>
            <div class="log-feed-wrap">
                <div class="feed-title">Agent Workflow Feed</div>
                <div id="log-sidebar">
                    <div class="log-box" style="border-left-color: var(--accent-green);">
                        <div class="log-time"><span style="color:var(--accent-green)">[INIT]</span><span>10:47:00</span></div>
                        <div class="log-task">System Boot Sequence</div>
                        <div class="log-msg">Agent interface clear. Anti-gravity physics engine initialized. Awaiting triggers.</div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script>
        // ============================================
        // DAY/NIGHT & AUDIO TOGGLES
        // ============================================
        let isDayMode = false;
        const themeToggle = document.getElementById('theme-toggle');
        const soundToggle = document.getElementById('sound-toggle');
        
        let audioContext;
        let soundEnabled = false;

        function playPing() {
            if (!soundEnabled || !audioContext) return;
            const osc = audioContext.createOscillator();
            const gain = audioContext.createGain();
            osc.connect(gain); gain.connect(audioContext.destination);
            osc.type = 'sine';
            osc.frequency.setValueAtTime(1000, audioContext.currentTime);
            osc.frequency.exponentialRampToValueAtTime(300, audioContext.currentTime + 0.2);
            gain.gain.setValueAtTime(0.05, audioContext.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.2);
            osc.start(); osc.stop(audioContext.currentTime + 0.2);
        }

        soundToggle.addEventListener('click', () => {
            soundEnabled = !soundEnabled;
            soundToggle.innerHTML = `<span>AUDIO: ${soundEnabled ? 'ON' : 'OFF'}</span>`;
            if (soundEnabled) {
                if(!audioContext) audioContext = new (window.AudioContext || window.webkitAudioContext)();
                playPing();
            }
        });

        // ============================================
        // THREE.JS - FLOATING MACHINERY ENGINE
        // ============================================
        const scene = new THREE.Scene();
        scene.fog = new THREE.FogExp2(0x0a1118, 0.04); // Default Night Fog

        const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 1000);
        const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        renderer.setSize(window.innerWidth, window.innerHeight);
        document.getElementById('canvas-container').appendChild(renderer.domElement);

        // --- MATERIALS ---
        const steelMaterial = new THREE.MeshStandardMaterial({
            color: 0x8892a0, metalness: 0.8, roughness: 0.3, flatShading: true
        });
        const darkIron = new THREE.MeshStandardMaterial({
            color: 0x222225, metalness: 0.9, roughness: 0.6
        });
        const brassMaterial = new THREE.MeshStandardMaterial({
            color: 0xc9a352, metalness: 0.7, roughness: 0.2
        });

        // --- GENERATE FLOATING PARTS ---
        const floatingParts = [];
        const geometries = [
            new THREE.TorusGeometry(1, 0.3, 16, 32),      // Ring / Washer
            new THREE.CylinderGeometry(0.4, 0.4, 2.5, 16), // Shaft / Pin
            new THREE.BoxGeometry(1.5, 0.2, 1.5),         // Metal Plate
            new THREE.CylinderGeometry(1.2, 1.2, 0.4, 6),  // Hex Nut
            new THREE.TorusGeometry(1.5, 0.4, 8, 12)       // Chunky Gear substitute
        ];
        const materials = [steelMaterial, darkIron, brassMaterial];

        for (let i = 0; i < 45; i++) {
            const geo = geometries[Math.floor(Math.random() * geometries.length)];
            const mat = materials[Math.floor(Math.random() * materials.length)];
            const part = new THREE.Mesh(geo, mat);

            // Random position in a wide area
            part.position.set(
                (Math.random() - 0.5) * 25,
                (Math.random() - 0.5) * 20,
                (Math.random() - 0.5) * 15 - 5
            );

            // Random rotation and velocity
            part.rotation.set(Math.random() * Math.PI, Math.random() * Math.PI, 0);
            part.userData = {
                rx: (Math.random() - 0.5) * 0.02,
                ry: (Math.random() - 0.5) * 0.02,
                vx: (Math.random() - 0.5) * 0.01,
                vy: (Math.random() - 0.5) * 0.01,
                vz: (Math.random() - 0.5) * 0.01
            };

            floatingParts.push(part);
            scene.add(part);
        }

        // --- LIGHTING (Dynamic for Day/Night) ---
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.2); // Night default
        scene.add(ambientLight);

        // Night Lights (Neon)
        const cyanLight = new THREE.PointLight(0x00F0FF, 5, 30);
        cyanLight.position.set(-8, 5, 5);
        scene.add(cyanLight);

        const goldLight = new THREE.PointLight(0xFFC72C, 4, 30);
        goldLight.position.set(8, -5, 5);
        scene.add(goldLight);

        // Day Light (Sun) - Initially hidden
        const sunLight = new THREE.DirectionalLight(0xffffff, 0);
        sunLight.position.set(10, 20, 10);
        scene.add(sunLight);

        camera.position.set(0, 0, 15);

        // --- DAY/NIGHT TOGGLE LOGIC ---
        themeToggle.addEventListener('click', () => {
            isDayMode = !isDayMode;
            document.body.classList.toggle('day-mode');
            
            if (isDayMode) {
                // Switch to Day
                scene.fog.color.setHex(0xcbd5e1);
                ambientLight.intensity = 1.5;
                cyanLight.intensity = 0;
                goldLight.intensity = 0;
                sunLight.intensity = 2.5;
            } else {
                // Switch to Night
                scene.fog.color.setHex(0x0a1118);
                ambientLight.intensity = 0.2;
                cyanLight.intensity = 5;
                goldLight.intensity = 4;
                sunLight.intensity = 0;
            }
            if(soundEnabled) playPing();
        });

        // --- ANIMATION LOOP ---
        function animate() {
            requestAnimationFrame(animate);

            // Animate each floating part
            floatingParts.forEach(part => {
                part.rotation.x += part.userData.rx;
                part.rotation.y += part.userData.ry;
                
                part.position.x += part.userData.vx;
                part.position.y += part.userData.vy;
                part.position.z += part.userData.vz;

                // Boundary bounce (Keep them in frame)
                if (Math.abs(part.position.x) > 15) part.userData.vx *= -1;
                if (Math.abs(part.position.y) > 12) part.userData.vy *= -1;
                if (part.position.z > 5 || part.position.z < -20) part.userData.vz *= -1;
            });

            // Gentle camera float
            camera.position.x = Math.sin(Date.now() * 0.0005) * 2;
            camera.position.y = Math.cos(Date.now() * 0.0004) * 1.5;
            camera.lookAt(0, 0, 0);

            renderer.render(scene, camera);
        }
        animate();

        window.addEventListener('resize', () => {
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        });

        // --- LIVE API LOG SIMULATION (Or connect to FastAPI) ---
        const logSidebar = document.getElementById('log-sidebar');
        
        // This function can be called by your WebSocket!
        function addLog(task, msg, type = 'action') {
            const box = document.createElement('div');
            box.className = 'log-box';

            let borderColor = 'var(--accent-cyan)';
            if (type === 'alert') borderColor = 'var(--accent-yellow)';
            if (type === 'success') borderColor = 'var(--accent-green)';
            
            box.style.borderLeftColor = borderColor;

            const now = new Date();
            const timeStr = now.getHours().toString().padStart(2,'0') + ':' + 
                            now.getMinutes().toString().padStart(2,'0') + ':' + 
                            now.getSeconds().toString().padStart(2,'0');

            box.innerHTML = `
                <div class="log-time"><span style="color:${borderColor}">[${type.toUpperCase()}]</span><span>${timeStr}</span></div>
                <div class="log-task">${task}</div>
                <div class="log-msg">${msg}</div>
            `;

            logSidebar.appendChild(box);
            document.querySelector('.log-feed-wrap').scrollTop = 999999;
            if(soundEnabled) playPing();
        }

        // Dummy data for visual testing
        setInterval(() => {
            if(Math.random() > 0.6) {
                addLog('Scanning Inventory', 'Analyzing heavy machinery parts in warehouse.', 'action');
            }
        }, 8000);
    </script>
</body>
</html>