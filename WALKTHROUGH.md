npm run dev -- --host# KRIA OS - User Walkthrough

Welcome to the KRIA OS Walkthrough. This guide explains how to demonstrate and use the two main pillars of the KRIA Medical Assist platform.

## 🏁 Preparation
1.  **Connect Phone**: Plug your Android device into the laptop via USB.
2.  **Start Web Server**: Run `npm run dev` in one terminal.
3.  **Port Forwarding**: Run `adb reverse tcp:5173 tcp:5173` to allow the phone to access the laptop's server.

---

## 🏗️ Demo 1: Blind Assist (Phone Only)
*Goal: Demonstrate hardware-level automation for low-vision users.*

1.  **Launch Automation**: In a terminal, run:
    ```bash
    python phone_mirror_automation.py
    ```
2.  **The Trigger**: Tap the **phone hardware screen** rapidly 3 times.
3.  **Observation**: 
    - The phone will automatically open the browser to the KRIA Assistant.
    - It will wait for the page to load and then **automatically click the "Voice" button**.
    - You should hear the "Calling Agent" state begin.
4.  **Stop**: Double-tap the phone screen to return home.

---

## 🏗️ Demo 2: Paralysis Assist (Laptop/Phone)
*Goal: Demonstrate AI eye-tracking for patients with limited movement.*

1.  **Open Mode**: Click the **Paralysis Assist** card on the laptop (or phone browser).
2.  **AI Initialization**:
    - Allow Camera Access.
    - Observe the blue "Eye Meters" in the corner corner.
3.  **Navigation**:
    - **Blink Left**: Notice the highlighter moves down the rows.
    - **Blink Right**: Notice the highlighter moves across the columns.
4.  **Selection**:
    - Select a phrase like **"WATER"** by closing **both eyes firmly** at once.
5.  **Observation**: 
    - The OS will display "WATER" in large text.
    - The laptop will **speak the request** out loud: *"Requesting Water"*.

---

## 🏗️ Demo 3: Wireless Mirroring
*Goal: Show how anyone on the network can connect.*

1.  **QR Code**: Scroll to the bottom of the home screen on your laptop.
2.  **Connect**: Scan the QR code with another mobile device on the same Wi-Fi.
3.  **Observation**: The second device now has full access to the KRIA OS and can act as a remote input for any assistant mode.

---

## 🏗️ Demo 4: Personaplex Voice & Automation (The Upgrade)
*Goal: Showcase the new 4-Tap Voice Assistant with "God Mode" automation.*

1.  **Start Backend**: You must run the python backend server for app automation:
    ```bash
    pip install -r backend/requirements.txt
    python backend/server.py
    ```
2.  **Port Forwarding**: Ensure port 8000 is also forwarded:
    ```bash
    adb reverse tcp:8000 tcp:8000
    ```
3.  **The Trigger**: Tap the **phone hardware screen** rapidly **4 times**.
4.  **Interaction**:
    - **"Guide me using camera"**: Opens the back camera with AI vision description (Simulated).
    - **"Book a cab to..."**: Attempts to launch Uber/Ola on the phone.
    - **"I am hungry"**: Launches food delivery apps.

---

## 🛠️ Troubleshooting
- **Camera not starting**: Ensure no other app (like Zoom or Teams) is using the webcam.
- **Blinks not registering**: Ensure your face is well-lit and you are positioned roughly in the center of the camera frame.
- **ADB Error**: Ensure "USB Debugging" is enabled in your phone's Developer Options.
