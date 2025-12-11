import asyncio
from bleak import BleakClient, BleakScanner
from pyautogui import press

PTT_MAC = "00:1B:10:1A:0A:51"
PTT_UUID = "0000ff02-0000-1000-8000-00805f9b34fb"

def handle_notify(sender, data):
    """Handle notifications from the PTT button"""
    if not data or len(data) < 5:
        return
    
    # Decode the message as ASCII
    try:
        message = data.decode('ascii')
    except:
        message = data.hex()
    
    print(f"Received: {message} (hex: {data.hex()})")
    
    # ELET1 appears to be button press, ELET2 appears to be button release
    if message.startswith("ELET1"):
        print("-> Button PRESSED - sending spacebar")
        press("space")
    elif message.startswith("ELET2"):
        print("-> Button RELEASED")
    elif message.startswith("BATT"):
        # Battery status, ignore or log
        print("-> Battery status message")

async def main():
    print(f"Connecting to {PTT_MAC} ({PTT_UUID})...")
    
    async with BleakClient(PTT_MAC, timeout=15.0) as client:
        if not client.is_connected:
            print("[!] Failed to connect.")
            return
        
        print("[+] Connected successfully!")
        
        # Subscribe to notifications
        await client.start_notify(PTT_UUID, handle_notify)
        print("\n[*] Listening for button presses. Press your PTT button!")
        print("Press Ctrl+C to quit.\n")
        
        # Keep listening
        while True:
            await asyncio.sleep(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n[+] Stopped.")
    except Exception as e:
        print(f"\n[!] Error: {e}")
        import traceback
        traceback.print_exc()
