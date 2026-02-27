# KRIA OS - AI-Powered Medical Assist OS

KRIA OS is a next-generation accessibility platform designed for individuals with diverse physical challenges. It leverages AI, Computer Vision, and Physical Automation to provide a seamless, hands-free experience.

## ✨ Feature Showcase
KRIA OS is a multi-modal operating system composed of 6 specialized assistants:

### 1. 👁️ Paralysis Mode: Neural-Blink Speller
*For users with limited mobility (locked-in syndrome, ALS).*
-   **Eye-Tracking**: Uses Google MediaPipe to detect blinks with 99% accuracy.
-   **Phrase Grid**: Rapidly select essential needs: **Water, Food, Washroom, Health Concern, Pain, and Medicine.**
-   **Gesture Control**:
    -   **Left Blink**: Move Row Down.
    -   **Right Blink**: Move Column Right.
    -   **Double Blink**: Select & Speak Phrase.
-   **Stabilization**: Built-in "Steady-Eye" to prevent accidental triggers.

### 2. 🦯 Blind Mode: Triple-Tap Automation
*For users with visual impairments.*
-   **Tactile Trigger**: Rapidly tap the screen **3 times** anywhere to trigger the assistant.
-   **Haptic Feedback**: Vibrates on every tap to confirm input.
-   **Auto-Redirect**: Instantly launches the **JotForm Voice Agent** for complex medical queries.

### 3. 🎙️ Personaplex: Neural Voice Engine (The "Jarvis")
*Hands-free control for everyone.*
-   **Wake Word**: "Open WhatsApp", "Scroll Down", "Go Home".
-   **Real-Time Action**: The phone reacts instantly to voice commands given to the laptop or phone.
-   **Visual Orb**: Pulse animation that breathes when listening and vibrates when speaking.

### 4. 🏥 General Medical Assist
*Quick access for emergency and general health support.*
-   **One-Touch WhatsApp**: Direct link to medical coordinators.
-   **AI Studio Integration**: Launches a specialized paralysis assist external tool.

### 5. 📷 Smart Vision Guide (Camera Mode)
*For environmental awareness.*
-   **Real-Time Guidance**: "Path is clear", "Person detected", "Scanning for currency".
-   **Object Detection**: Uses the camera to describe the scene (Simulated for demo).

### 🏥 6. Caretaker Agent (Post-Surgery Recovery)
*Proactive patient monitoring and emergency response.*
-   **Orchestration Simulation**: Visualizes a multi-agent system (Orchestrator, Specialist, Planner, Nurse) coordinating care.
-   **Local OCR**: Upload PDF or Photo of prescriptions/discharge summaries. Text is extracted locally via Tesseract OCR.
-   **Proactive Monitoring**: Agent checks in daily about pain, medication, and diet.
-   **Emergency Trigger**: Auto-detects "Shortness of breath" or "Severe pain" and **instantly dials emergency contacts** via ADB.
-   **Recovery Reports**: Generates professional markdown recovery summaries at the end of the session.

## 🛠️ Technical Setup

### Prerequisites
- Python 3.10+
- Node.js & NPM
- ADB (Android Debug Bridge) installed and in System PATH
- **Tesseract OCR Engine** installed (for Caretaker document parsing)

### 1. Web Application
```bash
npm install
npm run dev
```

### 🔗 Connectivity Guide (How to Connect Mobile)

#### Method A: Wi-Fi (Simplest)
*Ideal for quick demos when Laptop and Phone are on the same Wi-Fi network.*
1. **Start Server**: `npm run dev -- --host`
2. **Scan QR**: Scroll to the bottom of the laptop screen and scan the "Share / Connect Device" QR code with your phone.
3. **Launch**: The OS will open instantly on your mobile browser.

#### Method B: USB Bridge (Full Power & Stability)
*Recommended for full access to Neural-Blink, Blind-Tap, and Voice functionalities.*

**Phase 1: Unlock Developer Mode (One-Time Setup)**
1.  Open **Settings** on your Android Phone.
2.  Scroll to **About Phone**.
3.  Tap **Build Number** 7 times until it says "You are now a developer".
4.  Go back to **System** > **Developer Options**.
5.  Scroll down and enable **USB Debugging**.
6.  Connect your phone to the laptop via USB.
7.  Pop-up on Phone: Tap **"Allow"** (Check "Always allow from this computer").

**Phase 2: Link the Worlds (Port Bridging)**
Allow your phone to access the AI server running on your laptop.
```bash
adb reverse tcp:5173 tcp:5173
adb reverse tcp:8000 tcp:8000
```

**Phase 3: Launch the Core Systems**
Open 3 separate terminals to run the full OS suite:

**Terminal 1: The Visual Interface (Frontend)**
```bash
npm run dev -- --host
```

**Terminal 2: The Brain (AI Backend)**
```bash
# Install dependencies if needed: pip install -r backend/requirements.txt
python backend/server.py
```

**Terminal 3: The Nervous System (Touch & Mirror)**
This script mirrors your screen and enables Triple/Quad-tap gestures (3-tap for Jotform Assist, 4-tap for Voice Assistant).
```bash
python phone_mirror_automation.py
```
*(This will auto-launch `scrcpy` so you can see your phone screen on the laptop)*

**Phase 4: Experience the Magic**
- **Blind Mode**: Tap the phone screen **3 times** to launch the Blind Assistant.
- **Voice Mode**: Tap **4 times** to start the Neural Voice Engine.
- **Panic/Stop**: Tap **2 times** to stop any action and return Home.
- **Paralysis Mode**: Open `http://localhost:5173` on the phone (or laptop) to use Eye-Blink tracking.

### 🎤 Laptop Commander Mode
*Control your phone using your Laptop's Microphone and Speakers.*
1.  On your **Laptop**, open Chrome and go to: `http://localhost:5173/?mode=voice`
2.  Click "Allow" for Microphone permissions.
3.  **Speak Commands**: "Open WhatsApp", "Scroll Down", "Go Home".
4.  **Watch the Phone**: The actions will happen instantly on your mobile device via the neural bridge.

### 🖥️ Native Terminal Voice Mode
*For a developer-focused, purely command-line experience without the browser.*
1.  **Open Terminal**: Ensure you are in the project root.
2.  **Run Commander**:
    ```bash
    python terminal_voice_commander.py
    ```
3.  **Speak**: The terminal will listen and execute ADB commands directly.
    -   Try: *"Open YouTube"*, *"Scroll Down"*, *"Type Hello World"*, *"Go Home"*

#### Method C: Fully Wireless (Pro Mode)
*Run EVERYTHING (Website + Automation) without a single cable.*

**Phase 1: Wireless Pairing**
1.  **Initial Setup**: Connect your phone to the laptop via USB **once**.
2.  **Open Terminal** and run: `adb tcpip 5555`
3.  **Unplug**: Disconnect the USB cable.
4.  **Connect Wirelessly**: 
    - Find your Phone's IP Address (Settings > About Phone > Status).
    - Run: `adb connect <PHONE_IP_ADDRESS>:5555`
    - *Example: `adb connect 192.168.1.5:5555`*

**Phase 2: Link the Worlds (Wireless Bridge)**
Even wirelessly, we must bridge the ports so the phone can reach `localhost`.
```bash
adb reverse tcp:5173 tcp:5173
adb reverse tcp:8000 tcp:8000
```

**Phase 3: Launch the Core Systems**
(Same as Method B - Run these in 3 separate terminals)
1.  **Frontend**: `npm run dev -- --host`
2.  **Backend**: `python backend/server.py`
3.  **Automation**: `python phone_mirror_automation.py`

**Phase 4: Experience the Magic**
All functionalities (Blind-Tap, Voice-Tap, Eye-Blink) work exactly as in Method B!
- **Tap 3x**: Blind Assist
- **Tap 4x**: Voice Agent
- **Tap 2x**: Stop/Home


## 🧠 Technology Stack
- **Frontend**: React (Vite), Vanilla CSS (Premium Glassmorphism)
- **AI/Vision**: Google MediaPipe FaceLandmarker, TensorFlow.js
- **Automation**: Python, subprocess (ADB), threading
- **Feedback**: Web Speech API (TTS), Navigator Vibrate API

---
*Created for the KRIA Medical Hackathon - Empowering humanity through Zero-Touch technology.*
