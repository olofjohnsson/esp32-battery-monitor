SCRIPT_VERSION = "v2.0.0"

print(f"ESP32 Data Logger Script {SCRIPT_VERSION}\n")

import network
import time
import ujson as json
import urequests
from machine import ADC, Pin
import os

# --- Load Wi-Fi credentials and server URL ---
try:
    with open("credentials.json") as f:
        config = json.load(f)
        SSID = config["ssid"]
        PASSWORD = config["password"]
        SERVER_URL = config["server_url"]  # e.g., http://192.168.1.100:1111/api/store
except Exception as e:
    print("⚠️ Failed to load credentials.json:", e)
    raise SystemExit()

# --- Setup ADC ---
adc_pin = 2  # Change to your ADC pin number
adc = ADC(Pin(adc_pin))

# --- Buffer file for unsent data ---
BUFFER_FILE = "buffer.json"

def read_voltage():
    raw = adc.read()
    voltage = (raw / 8190) * 3.3  # Adjust for your ADC resolution
    return round(voltage, 3)

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(SSID, PASSWORD)

    print("Connecting to Wi-Fi...", end="")
    for _ in range(20):  # Try for 20 seconds
        if wlan.isconnected():
            print("\n✅ Connected! IP:", wlan.ifconfig()[0])
            return wlan
        print(".", end="")
        time.sleep(1)

    print("\n❌ Failed to connect to Wi-Fi.")
    wlan.active(False)
    return None

def send_data(voltage, timestamp):
    try:
        payload = {
            "voltage": voltage,
            "device_id": "esp32-001",
            "channel": 0
        }
        print("📡 Sending data:", payload)
        response = urequests.post(SERVER_URL, json=payload)
        print("✅ Server response:", response.text)
        response.close()
        return True
    except Exception as e:
        print("⚠️ Failed to send data:", e)
        return False

def save_to_buffer(entry):
    if BUFFER_FILE in os.listdir():
        with open(BUFFER_FILE, "r") as f:
            buffer = json.load(f)
    else:
        buffer = []

    buffer.append(entry)

    with open(BUFFER_FILE, "w") as f:
        json.dump(buffer, f)
    print("💾 Data saved locally.")

def flush_buffer():
    if BUFFER_FILE not in os.listdir():
        return

    print("📤 Flushing buffered data...")
    with open(BUFFER_FILE, "r") as f:
        buffer = json.load(f)

    success_entries = []
    for entry in buffer:
        if send_data(entry["voltage"], entry["timestamp"]):
            success_entries.append(entry)

    # Remove successfully sent entries
    buffer = [e for e in buffer if e not in success_entries]

    if buffer:
        print(f"⚠️ {len(buffer)} entries remain unsent.")
    else:
        print("✅ All buffered data sent!")

    with open(BUFFER_FILE, "w") as f:
        json.dump(buffer, f)

# --- Main Loop ---
try:
    wlan = connect_wifi()
    if wlan:
        flush_buffer()

    while True:
        voltage = read_voltage()
        timestamp = time.time()  # Or use RTC if configured
        print(f"🔋 Voltage: {voltage} V @ {timestamp}")

        if wlan and wlan.isconnected():
            if send_data(voltage, timestamp):
                pass  # Data sent successfully
            else:
                save_to_buffer({"voltage": voltage, "timestamp": timestamp})
        else:
            print("📴 No Wi-Fi, buffering data.")
            save_to_buffer({"voltage": voltage, "timestamp": timestamp})

        time.sleep(10)  # Sample every 10 seconds

except KeyboardInterrupt:
    print("🛑 Stopped by user.")
