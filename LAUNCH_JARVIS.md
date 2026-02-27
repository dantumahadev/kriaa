# How to Launch JARVIS (Laptop Voice Controller)

The "Jarvis" module is a standalone Python script that uses your **laptop's microphone** to control your connected Android phone via ADB.

## Prerequisites
1. **Connect your Phone** via USB.
2. Ensure **USB Debugging** is enabled.
3. Your phone/laptop volume should be audible.

## Start Jarvis
Run the following command in your terminal:

```bash
python backend/jarvis.py
```

## Features
- **Always Listening**: No wake word needed (for now), just speak commands.
- **Context Aware**: Checks for notifications when opening messaging apps.
- **Commands**:
  - "Open WhatsApp / YouTube / Chrome"
  - "Scroll down / up"
  - "Go Home", "Go Back"
  - "Type [message]"

## Stopping
Press `Ctrl + C` in the terminal to stop the assistant.
