import time
import webbrowser
from pynput import mouse
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import threading

# Configuration
TARGET_URL = "https://www.jotform.com/agent/019a4add964b79f3aa038b973d1fea25967d"
CLICK_THRESHOLD = 3
TIME_WINDOW = 1.0  # Seconds to register 3 clicks

class LaptopAssistant:
    def __init__(self):
        self.click_times = []
        self.is_running_automation = False
        self.is_setup_done = False # New state to track if blind mode was "activated"
        print("--- Global Medical Assist Automation ---")
        print("Waiting for you to activate 'Blind Mode' in the app...")

    def on_click(self, x, y, button, pressed):
        # Trigger on release (pressed=False) to ensure the click is complete
        if not pressed and button == mouse.Button.left:
            now = time.time()
            # Increased window to 1.5s for more reliability
            self.click_times = [t for t in self.click_times if now - t < 1.5]
            self.click_times.append(now)
            print(f"DEBUG: Click registered at ({x}, {y}). Total: {len(self.click_times)}")

            if len(self.click_times) >= CLICK_THRESHOLD:
                print("\n[GLOBAL EVENT] TRIPLE CLICK DETECTED! Launching Assistant...")
                self.click_times = []
                if not self.is_running_automation:
                    threading.Thread(target=self.launch_and_select_voice).start()

    def launch_and_select_voice(self):
        self.is_running_automation = True
        driver = None
        try:
            print("Action Triggered: Automating Voice Mode...")
            chrome_options = Options()
            chrome_options.add_argument("--use-fake-ui-for-media-stream") 
            # chrome_options.add_argument("--headless") # Uncomment if you want it silent background
            
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            driver.get(TARGET_URL)
            wait = WebDriverWait(driver, 15)
            
            # Step 1: Open Sidebar Menu
            print("Opening Agent Channels Menu...")
            try:
                # Based on the user screenshot, looking for the menu/grid button
                menu_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'menu')] | //div[contains(@class, 'grid')] | //button[@aria-label='Menu']")))
                menu_btn.click()
                time.sleep(1.5)
            except:
                print("Menu icon search failed, attempting direct Voice selection...")

            # Step 2: Click Voice
            try:
                voice_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[text()='Voice' or contains(text(), 'Voice')]")))
                voice_btn.click()
                print(">>> Voice Mode Activated Success! <<<")
            except:
                print("Could not find Voice button. Please ensure the Jotform agent is configured correctly.")

            # Keep alive for interaction
            while len(driver.window_handles) > 0:
                time.sleep(2)

        except Exception as e:
            print(f"Automation sequence error: {e}")
        finally:
            self.is_running_automation = False
            if driver:
                try: driver.quit()
                except: pass

    def start(self):
        print("Background Monitoring ACTIVE.")
        print("You can now minimize the app. Triple-clicking ANYWHERE on your laptop will trigger the assistant.")
        with mouse.Listener(on_click=self.on_click) as listener:
            listener.join()

if __name__ == "__main__":
    assistant = LaptopAssistant()
    assistant.start()
