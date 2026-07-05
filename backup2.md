<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mewar Hi-Tech | Jaw Crusher Twin</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Oswald:wght@500;600;700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500;600&display=swap');

        :root {
            --bg-gradient: radial-gradient(circle at center, #0a1118 0%, #020305 100%);
            --panel-bg: rgba(8, 12, 18, 0.7);
            --panel-border: rgba(0, 240, 255, 0.3);
            --text-main: #ffffff;
            --text-muted: #8892a0;
            --accent-cyan: #00F0FF;
            --accent-yellow: #FFC72C;
            --accent-green: #3DDC84;
            --log-bg: rgba(255, 255, 255, 0.05);
            --grid-color: rgba(0, 240, 255, 0.04);
        }

        body.day-mode {
            --bg-gradient: radial-gradient(circle at center, #e2e8f0 0%, #94a3b8 100%);
            --panel-bg: rgba(255, 255, 255, 0.7);
            --panel-border: rgba(15, 23, 42, 0.2);
            --text-main: #0f172a;
            --text-muted: #475569;
            --accent-cyan: #0284c7; 
            --accent-yellow: #d97706; 
            --accent-green: #16a34a;
            --log-bg: rgba(0, 0, 0, 0.06);
            --grid-color: rgba(15, 23, 42, 0.05);
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { width: 100%; height: 100vh; overflow: hidden; background: var(--bg-gradient); font-family: 'Inter', sans-serif; color: var(--text-main); transition: background 0.8s ease; }
        #canvas-container { position: absolute; inset: 0; width: 100%; height: 100%; cursor: ns-resize; }
        canvas { display: block; }

        #grid-overlay {
            position: absolute; inset: 0; pointer-events: none; z-index: 4;
            background-image: linear-gradient(var(--grid-color) 1px, transparent 1px), linear-gradient(90deg, var(--grid-color) 1px, transparent 1px);
            background-size: 50px 50px; transition: all 0.8s ease;
        }

        #scroll-hint {
            position: absolute; bottom: 40px; left: 50%; transform: translateX(-50%); z-index: 20; color: var(--accent-cyan); 
            font-family: 'JetBrains Mono', monospace; font-size: 14px; text-transform: uppercase; letter-spacing: 2px;
            display: flex; flex-direction: column; align-items: center; pointer-events: none; opacity: 0.8; animation: bounce 2s infinite; text-shadow: 0 0 10px rgba(0,240,255,0.5);
        }
        @keyframes bounce { 0%, 100% { transform: translate(-50%, 0); } 50% { transform: translate(-50%, -10px); } }
        
        .mouse-icon { width: 26px; height: 40px; border: 2px solid var(--accent-cyan); border-radius: 13px; margin-bottom: 10px; position: relative; box-shadow: 0 0 10px rgba(0,240,255,0.2); }
        .mouse-wheel { width: 4px; height: 8px; background: var(--accent-cyan); border-radius: 2px; position: absolute; top: 6px; left: 50%; transform: translateX(-50%); animation: scrollWheel 2s infinite; box-shadow: 0 0 5px var(--accent-cyan); }
        @keyframes scrollWheel { 0% { top: 6px; opacity: 1; } 100% { top: 20px; opacity: 0; } }

        .controls-wrapper { position: absolute; top: 24px; left: 28px; z-index: 20; display: flex; gap: 12px; }
        .btn-control {
            background: var(--panel-bg); border: 1px solid var(--panel-border); color: var(--text-main); padding: 10px 16px; border-radius: 6px; font-size: 12px; font-weight: 600; cursor: pointer;
            font-family: 'JetBrains Mono', monospace; text-transform: uppercase; letter-spacing: 1px; box-shadow: 0 4px 10px rgba(0,0,0,0.2); transition: all 0.3s ease; backdrop-filter: blur(10px);
        }
        .btn-control:hover { border-color: var(--accent-cyan); transform: translateY(-2px); box-shadow: 0 6px 15px rgba(0,240,255,0.2); }

        #ui-layer {
            position: absolute; top: 0; right: 0; width: 100%; height: 100%; pointer-events: none; display: flex; flex-direction: column;
            justify-content: space-between; padding: 30px; z-index: 10; transition: all 0.5s ease;
        }
        #ui-layer.is-fullscreen { padding: 0; }
        
        .panel {
            width: 400px; max-height: calc(100vh - 60px); display: flex; flex-direction: column; align-self: flex-end;
            background: var(--panel-bg); border: 1px solid var(--panel-border); border-radius: 12px; box-shadow: -10px 0 40px rgba(0,0,0,0.5);
            pointer-events: auto; overflow: hidden; backdrop-filter: blur(25px); -webkit-backdrop-filter: blur(25px); transition: all 0.4s cubic-bezier(0.25, 0.8, 0.25, 1);
        }

        #ui-layer.is-fullscreen .panel {
            width: 100%; max-height: 100vh; height: 100vh; border-radius: 0; border: none; align-self: stretch;
            background: rgba(8, 12, 18, 0.75); backdrop-filter: blur(30px); -webkit-backdrop-filter: blur(30px);
        }
        body.day-mode #ui-layer.is-fullscreen .panel { background: rgba(255, 255, 255, 0.75); }

        .panel-header { background: linear-gradient(90deg, var(--accent-cyan) 0%, var(--accent-yellow) 100%); height: 4px; }
        .brand-block { padding: 24px; border-bottom: 1px solid var(--panel-border); display: flex; justify-content: space-between; align-items: flex-start; }
        .brand-titles h1 { font-family: 'Oswald', sans-serif; font-size: 26px; margin: 0 0 4px; text-transform: uppercase; color: var(--text-main); letter-spacing: 1px;}
        .brand-tag { font-family: 'JetBrains Mono', monospace; font-size: 11px; color: var(--accent-cyan); text-transform: uppercase; font-weight: 600; letter-spacing: 2px;}

        .btn-expand {
            background: transparent; border: 1px solid var(--accent-cyan); color: var(--accent-cyan); padding: 6px 12px; border-radius: 4px; cursor: pointer; 
            font-family: 'JetBrains Mono', monospace; font-size: 11px; font-weight: 600; transition: all 0.3s;
        }
        .btn-expand:hover { background: var(--accent-cyan); color: #000; }

        .status-strip { display: flex; gap: 10px; padding: 16px 24px; border-bottom: 1px solid var(--panel-border); }
        .status-chip { flex: 1; background: var(--log-bg); border: 1px solid rgba(255,255,255,0.05); border-radius: 6px; padding: 12px; }
        .status-chip .label { font-family: 'JetBrains Mono', monospace; font-size: 10px; color: var(--text-muted); text-transform: uppercase; margin-bottom: 6px; font-weight: 600;}
        .status-chip .value { font-family: 'Oswald', sans-serif; font-size: 18px; font-weight: 600; color: var(--text-main); }
        
        .log-feed-wrap { flex: 1; overflow-y: auto; padding: 20px 24px; }
        .log-feed-wrap::-webkit-scrollbar { width: 4px; }
        .log-feed-wrap::-webkit-scrollbar-thumb { background: var(--accent-cyan); border-radius: 2px; }

        .feed-title { font-family: 'JetBrains Mono', monospace; font-size: 11px; color: var(--text-muted); text-transform: uppercase; margin-bottom: 15px; font-weight: 600; letter-spacing: 1px;}
        
        .log-box {
            background: var(--log-bg); border: 1px solid rgba(255,255,255,0.05); border-left: 3px solid var(--accent-cyan); padding: 16px; margin-bottom: 12px;
            border-radius: 0 8px 8px 0; animation: slideIn 0.3s ease-out forwards;
        }
        @keyframes slideIn { from { transform: translateX(20px); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
        
        .log-time { font-family: 'JetBrains Mono', monospace; color: var(--text-muted); font-size: 10px; font-weight: 600; display: flex; justify-content: space-between; margin-bottom: 8px; }
        .log-task { font-weight: 700; font-size: 14px; color: var(--text-main); margin-bottom: 6px; font-family: 'Inter', sans-serif;}
        .log-msg { font-size: 13px; color: #a1a1aa; line-height: 1.5; font-weight: 400;}

        #nameplate { position: absolute; bottom: 30px; left: 30px; pointer-events: none; z-index: 8; transition: opacity 0.3s; }
        #ui-layer.is-fullscreen ~ #nameplate { opacity: 0; }
        #nameplate .name { font-size: 56px; font-weight: 700; color: var(--text-main); text-transform: uppercase; line-height: 0.9; font-family: 'Oswald', sans-serif; text-shadow: 0 10px 30px rgba(0,0,0,0.5);}
        #nameplate .name em { color: var(--accent-yellow); font-style: normal; display: block; }
    </style>
</head>
<body>
    <div id="grid-overlay"></div>
    <div id="canvas-container"></div>

    <div class="controls-wrapper">
        <button class="btn-control" id="theme-toggle">DAY / NIGHT</button>
        <button class="btn-control" id="sound-toggle">AUDIO: OFF</button>
    </div>

    <div id="scroll-hint">
        <div class="mouse-icon"><div class="mouse-wheel"></div></div>
        Scroll to Assemble
    </div>

    <div id="nameplate">
        <div class="name">MEWAR<br><em>HI-TECH</em></div>
    </div>

    <div id="ui-layer">
        <div class="panel">
            <div class="panel-header"></div>
            <div class="brand-block">
                <div class="brand-titles">
                    <h1>Mewar Hi-Tech</h1>
                    <div class="brand-tag">AI Operations Agent</div>
                </div>
                <button class="btn-expand" id="expand-btn">⛶ EXPAND</button>
            </div>
            <div class="status-strip">
                <div class="status-chip">
                    <div class="label">Database Sync</div>
                    <div class="value" style="color: var(--accent-green);">Connected</div>
                </div>
                <div class="status-chip">
                    <div class="label">Machine Status</div>
                    <div class="value" id="status-val" style="color: var(--accent-yellow);">Floating</div>
                </div>
            </div>
            <div class="log-feed-wrap">
                <div class="feed-title">Live AI Activity</div>
                <div id="log-sidebar">
                    <div class="log-box" style="border-left-color: var(--accent-green);">
                        <div class="log-time"><span style="color:var(--accent-green)">[SYSTEM]</span><span>Just Now</span></div>
                        <div class="log-task">Agent Initialized</div>
                        <div class="log-msg">Ready to track Mewar ERP Inventory and manage Purchase Orders.</div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script>
        // ============================================
        // UI, FULLSCREEN & AUDIO LOGIC
        // ============================================
        const expandBtn = document.getElementById('expand-btn');
        const uiLayer = document.getElementById('ui-layer');
        let isFullscreen = false;
        expandBtn.addEventListener('click', () => {
            isFullscreen = !isFullscreen;
            if (isFullscreen) { uiLayer.classList.add('is-fullscreen'); expandBtn.innerText = "✖ CLOSE"; } 
            else { uiLayer.classList.remove('is-fullscreen'); expandBtn.innerText = "⛶ EXPAND"; }
        });

        let isDayMode = false;
        document.getElementById('theme-toggle').addEventListener('click', () => {
            isDayMode = !isDayMode; document.body.classList.toggle('day-mode');
            if (isDayMode) {
                scene.fog.color.setHex(0xcbd5e1); ambientLight.intensity = 2.0;
                cyanLight.intensity = 0; goldLight.intensity = 0; sunLight.intensity = 3.0;
            } else {
                scene.fog.color.setHex(0x0a1118); ambientLight.intensity = 0.5;
                cyanLight.intensity = 6; goldLight.intensity = 5; sunLight.intensity = 0;
            }
        });

        let audioContext; let soundEnabled = false;
        function playClink() {
            if (!soundEnabled || !audioContext) return;
            const osc = audioContext.createOscillator(); const gain = audioContext.createGain();
            osc.type = 'square'; osc.frequency.setValueAtTime(400 + Math.random() * 400, audioContext.currentTime);
            osc.frequency.exponentialRampToValueAtTime(100, audioContext.currentTime + 0.1);
            gain.gain.setValueAtTime(0.08, audioContext.currentTime); gain.gain.exponentialRampToValueAtTime(0.001, audioContext.currentTime + 0.1);
            osc.connect(gain); gain.connect(audioContext.destination); osc.start(); osc.stop(audioContext.currentTime + 0.1);
        }
        document.getElementById('sound-toggle').addEventListener('click', (e) => {
            soundEnabled = !soundEnabled; e.target.innerText = `AUDIO: ${soundEnabled ? 'ON' : 'OFF'}`;
            if (soundEnabled && !audioContext) audioContext = new (window.AudioContext || window.webkitAudioContext)();
        });

        // ============================================
        // PROCEDURAL HEAVY JAW CRUSHER (Detailed)
        // ============================================
        const scene = new THREE.Scene(); scene.fog = new THREE.FogExp2(0x0a1118, 0.03);
        const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 1000);
        const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2)); renderer.setSize(window.innerWidth, window.innerHeight);
        document.getElementById('canvas-container').appendChild(renderer.domElement);

        // Precise Materials from the Image
        const brightBlueMat = new THREE.MeshStandardMaterial({ color: 0x1B3B8A, metalness: 0.3, roughness: 0.5 }); 
        const pureCreamMat = new THREE.MeshStandardMaterial({ color: 0xF4EFE6, metalness: 0.1, roughness: 0.8 });  
        const darkSteelMat = new THREE.MeshStandardMaterial({ color: 0x222222, metalness: 0.8, roughness: 0.4 });  
        const boltMat = new THREE.MeshStandardMaterial({ color: 0x999999, metalness: 0.9, roughness: 0.3 });  

        const machineParts = [];
        const masterGroup = new THREE.Group(); masterGroup.position.y = 1; scene.add(masterGroup);

        function registerPart(geometry, material, targetPos, targetRot) {
            const mesh = new THREE.Mesh(geometry, material);
            const floatPos = new THREE.Vector3((Math.random() - 0.5) * 35, (Math.random() - 0.5) * 25, (Math.random() - 0.5) * 15);
            mesh.position.copy(floatPos);
            const floatRot = new THREE.Euler(Math.random()*Math.PI, Math.random()*Math.PI, Math.random()*Math.PI);
            mesh.rotation.copy(floatRot);

            mesh.userData = {
                targetPos: new THREE.Vector3(...targetPos), targetQuat: new THREE.Quaternion().setFromEuler(new THREE.Euler(...targetRot)),
                vx: (Math.random() - 0.5) * 0.04, vy: (Math.random() - 0.5) * 0.04, vz: (Math.random() - 0.5) * 0.04,
                rx: (Math.random() - 0.5) * 0.03, ry: (Math.random() - 0.5) * 0.03,
                currentFloatPos: floatPos.clone(), currentFloatQuat: new THREE.Quaternion().setFromEuler(floatRot), lastCollision: 0
            };
            machineParts.push(mesh); masterGroup.add(mesh);
        }

        // --- 1. HEAVY CREAM BASE & SIDE HOUSINGS ---
        // Main bed
        registerPart(new THREE.BoxGeometry(4.8, 1.0, 3.2), pureCreamMat, [0, -1.0, 0.5], [0, 0, 0]); 
        // Front toggle arms (extending forward)
        registerPart(new THREE.BoxGeometry(0.8, 0.6, 2.5), pureCreamMat, [-1.5, -1.2, 3.0], [0, 0, 0]); 
        registerPart(new THREE.BoxGeometry(0.8, 0.6, 2.5), pureCreamMat, [1.5, -1.2, 3.0], [0, 0, 0]); 

        // Left & Right Bearing Housings (Side Cream Boxes)
        registerPart(new THREE.BoxGeometry(1.2, 2.2, 2.5), pureCreamMat, [-3.0, 0.6, 0.5], [0, 0, 0]);
        registerPart(new THREE.BoxGeometry(1.2, 2.2, 2.5), pureCreamMat, [3.0, 0.6, 0.5], [0, 0, 0]);

        // Prominent Side Bolts (3 on each side)
        const boltGeo = new THREE.CylinderGeometry(0.18, 0.18, 0.4, 16);
        for(let i=0; i<3; i++) {
            let by = 0.0 + (i * 0.6);
            // Left side bolts
            registerPart(boltGeo, boltMat, [-3.6, by, 0.5], [0, 0, Math.PI/2]);
            // Right side bolts
            registerPart(boltGeo, boltMat, [3.6, by, 0.5], [0, 0, Math.PI/2]);
        }

        // --- 2. BLUE SLANTED JAW BODY & RIBS ---
        // Back slanted plate
        registerPart(new THREE.BoxGeometry(4.6, 2.8, 0.8), brightBlueMat, [0, 1.4, -1.2], [Math.PI/8, 0, 0]);
        // Top cylindrical housing
        registerPart(new THREE.CylinderGeometry(0.6, 0.6, 4.6, 32), brightBlueMat, [0, 2.6, -1.8], [0, 0, Math.PI/2]);

        // Vertical Ribs on the slanted back
        const ribGeo = new THREE.BoxGeometry(0.3, 3.0, 1.2);
        for(let i=0; i<5; i++) {
            let px = -1.8 + (i * 0.9);
            registerPart(ribGeo, brightBlueMat, [px, 1.5, -1.0], [Math.PI/8, 0, 0]); 
        }

        // --- 3. LARGE RIBBED BLUE FLYWHEELS ---
        // To fake grooves without textures, we use a slightly smaller dark inner cylinder and larger blue outer rings
        const wheelCore = new THREE.CylinderGeometry(2.4, 2.4, 1.2, 48);
        const wheelRim = new THREE.TorusGeometry(2.4, 0.15, 16, 48);
        
        // Left Wheel Group
        registerPart(wheelCore, darkSteelMat, [-4.6, 1.2, -0.5], [Math.PI/2, 0, Math.PI/2]); 
        registerPart(wheelRim, brightBlueMat, [-4.1, 1.2, -0.5], [0, Math.PI/2, 0]); // Outer rim edge
        registerPart(wheelRim, brightBlueMat, [-5.1, 1.2, -0.5], [0, Math.PI/2, 0]); // Inner rim edge
        
        // Right Wheel Group
        registerPart(wheelCore, darkSteelMat, [4.6, 1.2, -0.5], [Math.PI/2, 0, Math.PI/2]); 
        registerPart(wheelRim, brightBlueMat, [4.1, 1.2, -0.5], [0, Math.PI/2, 0]);
        registerPart(wheelRim, brightBlueMat, [5.1, 1.2, -0.5], [0, Math.PI/2, 0]);

        // Main Center Shaft
        registerPart(new THREE.CylinderGeometry(0.35, 0.35, 10.5, 32), darkSteelMat, [0, 1.2, -0.5], [0, 0, Math.PI/2]);

        // --- 4. HANGING COIL SPRINGS (Toggle Mechanism) ---
        const springRingGeo = new THREE.TorusGeometry(0.3, 0.1, 16, 24);
        for(let i=0; i<10; i++) {
            let py = -1.8 - (i * 0.22);
            registerPart(springRingGeo, brightBlueMat, [-1.5, py, 3.8], [Math.PI/2, 0, 0]); // Left Spring
            registerPart(springRingGeo, brightBlueMat, [1.5, py, 3.8], [Math.PI/2, 0, 0]);  // Right Spring
        }
        // Spring core shafts (Dark metal inside springs)
        registerPart(new THREE.CylinderGeometry(0.12, 0.12, 2.8, 8), darkSteelMat, [-1.5, -2.8, 3.8], [0, 0, 0]);
        registerPart(new THREE.CylinderGeometry(0.12, 0.12, 2.8, 8), darkSteelMat, [1.5, -2.8, 3.8], [0, 0, 0]);

        // --- SCROLL LOGIC ---
        let scrollProgress = 0; 
        const statusVal = document.getElementById('status-val');
        const scrollHint = document.getElementById('scroll-hint');

        window.addEventListener('wheel', (e) => {
            scrollProgress += e.deltaY * 0.0015; 
            scrollProgress = Math.max(0, Math.min(1, scrollProgress)); 

            if (scrollProgress === 0) { 
                statusVal.innerText = "Floating Parts"; statusVal.style.color = "var(--accent-yellow)"; scrollHint.style.opacity = "0.8"; 
            } else if (scrollProgress === 1) { 
                statusVal.innerText = "Machine Assembled"; statusVal.style.color = "var(--accent-green)"; scrollHint.style.opacity = "0"; 
            } else { 
                statusVal.innerText = "Assembling..."; statusVal.style.color = "var(--accent-cyan)"; scrollHint.style.opacity = "0"; 
            }
        });

        // --- LIGHTING ---
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.7); scene.add(ambientLight);
        const cyanLight = new THREE.PointLight(0x00F0FF, 5, 30); cyanLight.position.set(-8, 8, 8); scene.add(cyanLight);
        const goldLight = new THREE.PointLight(0xFFC72C, 4, 30); goldLight.position.set(8, -5, 5); scene.add(goldLight);
        const sunLight = new THREE.DirectionalLight(0xffffff, 0); sunLight.position.set(10, 20, 10); scene.add(sunLight);

        // Positioned camera nicely to see side boxes, springs, and front arms
        camera.position.set(0, 2.5, 16);

        // --- ANIMATION LOOP ---
        function animate() {
            requestAnimationFrame(animate);

            if (scrollProgress === 1) {
                masterGroup.rotation.y -= 0.003; // Slow majestic spin when assembled
            } else {
                masterGroup.rotation.y += (0 - masterGroup.rotation.y) * 0.1;
            }

            for (let i = 0; i < machineParts.length; i++) {
                const part = machineParts[i];
                const ud = part.userData;

                if (scrollProgress === 0) {
                    ud.currentFloatPos.x += ud.vx; ud.currentFloatPos.y += ud.vy; ud.currentFloatPos.z += ud.vz;
                    const rotDelta = new THREE.Quaternion().setFromEuler(new THREE.Euler(ud.rx, ud.ry, 0));
                    ud.currentFloatQuat.multiplyQuaternions(rotDelta, ud.currentFloatQuat);

                    if (Math.abs(ud.currentFloatPos.x) > 16) ud.vx *= -1;
                    if (Math.abs(ud.currentFloatPos.y) > 12) ud.vy *= -1;
                    if (ud.currentFloatPos.z > 5 || ud.currentFloatPos.z < -15) ud.vz *= -1;

                    for (let j = i + 1; j < machineParts.length; j++) {
                        const otherPart = machineParts[j];
                        if (ud.currentFloatPos.distanceTo(otherPart.userData.currentFloatPos) < 2.5) { 
                            const now = Date.now();
                            ud.vx *= -1; ud.vy *= -1;
                            otherPart.userData.vx *= -1; otherPart.userData.vy *= -1;
                            if (now - ud.lastCollision > 150) { playClink(); ud.lastCollision = now; }
                        }
                    }

                    part.position.copy(ud.currentFloatPos);
                    part.quaternion.copy(ud.currentFloatQuat);
                } else {
                    part.position.lerpVectors(ud.currentFloatPos, ud.targetPos, scrollProgress);
                    part.quaternion.slerpQuaternions(ud.currentFloatQuat, ud.targetQuat, scrollProgress);
                }
            }

            // Slight panning with time
            camera.position.x = Math.sin(Date.now() * 0.0002) * 1.5;
            camera.position.y = 2.5 + Math.cos(Date.now() * 0.00015) * 1.0;
            camera.lookAt(0, 1.5, 0);

            renderer.render(scene, camera);
        }
        animate();

        window.addEventListener('resize', () => {
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        });
    </script>
</body>
</html>