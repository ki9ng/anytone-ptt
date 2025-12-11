#!/usr/bin/env python3
"""
Anytone PTT Bluetooth Controller
Uses bleak library to connect to Anytone/ELET PTT buttons and trigger keyboard events.
This script holds down a key (default: Ctrl) while the PTT button is pressed,
and releases it when the button is released - perfect for push-to-talk applications.
"""
import asyncio
import sys
from bleak import BleakClient, BleakScanner
import pyautogui

# Configuration
PTT_MAC = None  # Set to your device MAC address, or None to auto-discover
PTT_UUID = "0000ff02-0000-1000-8000-00805f9b34fb"  # ELET-PTT notify characteristic
KEY_TO_HOLD = "ctrl"  # Key to hold while PTT button is pressed

# Global state tracking
button_pressed = False


def handle_notify(sender, data):
    """
    Handle notifications from the PTT button.
    
    The ELET-PTT device sends ASCII messages:
    - ELET1: Button pressed
    - ELET2: Button released
    - BATTd: Battery status (ignored)
    
    Args:
        sender: The characteristic that sent the notification
        data: Raw bytes received from the device
    """
    global button_pressed
    
    # Validate data
    if not data or len(data) < 5:
        return
    
    # Decode the message as ASCII
    try:
        message = data.decode('ascii')
    except UnicodeDecodeError:
        # If not valid ASCII, use hex representation for debugging
        message = data.hex()
    
    print(f"Received: {message}")
    
    # Handle button press
    if message.startswith("ELET1"):
        if not button_pressed:
            print(f"-> Button PRESSED - holding '{KEY_TO_HOLD}'")
            pyautogui.keyDown(KEY_TO_HOLD)
            button_pressed = True
    
    # Handle button release
    elif message.startswith("ELET2"):
        if button_pressed:
            print(f"-> Button RELEASED - releasing '{KEY_TO_HOLD}'")
            pyautogui.keyUp(KEY_TO_HOLD)
            button_pressed = False
    
    # Battery status messages are ignored
    elif message.startswith("BATT"):
        pass


async def find_ptt_device():
    """
    Scan for ELET-PTT devices and return the selected MAC address.
    
    If only one device is found, it's automatically selected.
    If multiple devices are found, the user is prompted to choose.
    
    Returns:
        str: MAC address of selected device, or None if scanning cancelled
    """
    print("Scanning for ELET-PTT devices...")
    devices = await BleakScanner.discover(timeout=5.0)
    
    # Filter for ELET-PTT devices
    ptt_devices = []
    for device in devices:
        if device.name and "ELET-PTT" in device.name:
            ptt_devices.append(device)
            print(f"Found: {device.address} - {device.name}")
    
    if not ptt_devices:
        print("No ELET-PTT devices found.")
        return None
    
    # Auto-select if only one device
    if len(ptt_devices) == 1:
        return ptt_devices[0].address
    
    # Prompt user to choose from multiple devices
    print("\nMultiple devices found. Please choose:")
    for i, device in enumerate(ptt_devices):
        print(f"{i+1}. {device.address} - {device.name}")
    
    try:
        choice = input("Enter number (or 'q' to quit): ")
        if choice.lower() == 'q':
            return None
        idx = int(choice) - 1
        if 0 <= idx < len(ptt_devices):
            return ptt_devices[idx].address
        else:
            print("Invalid choice.")
            return None
    except (ValueError, KeyboardInterrupt):
        print("\nCancelled.")
        return None


async def connect_and_listen():
    """
    Connect to the PTT device and listen for button press notifications.
    Keeps trying to reconnect if connection is lost.
    """
    global PTT_MAC, button_pressed
    
    # Auto-discover if MAC not set
    if not PTT_MAC:
        PTT_MAC = await find_ptt_device()
        if not PTT_MAC:
            print("\n[*] No device selected. Waiting for manual retry...")
            print("[*] Press Ctrl+C to quit, or restart the script to scan again.")
            # Wait forever - don't exit
            try:
                while True:
                    await asyncio.sleep(60)
            except KeyboardInterrupt:
                return
    
    print(f"\nConnecting to {PTT_MAC}...")
    
    try:
        async with BleakClient(PTT_MAC, timeout=15.0) as client:
            if not client.is_connected:
                print("[!] Failed to connect.")
                print("[*] Will keep trying... Press Ctrl+C to quit.")
                # Wait and don't exit - user can restart manually
                try:
                    while True:
                        await asyncio.sleep(60)
                except KeyboardInterrupt:
                    return
            
            print("[+] Connected successfully!")
            print(f"[*] PTT will hold '{KEY_TO_HOLD}' key while pressed")
            
            # Subscribe to notifications
            await client.start_notify(PTT_UUID, handle_notify)
            print("\n[*] Listening for button presses...")
            print("[*] Press Ctrl+C to quit.\n")
            
            # Keep listening indefinitely
            try:
                while True:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                # Clean exit - release key if held
                if button_pressed:
                    print("\nReleasing held key...")
                    pyautogui.keyUp(KEY_TO_HOLD)
                raise
                
    except Exception as e:
        print(f"[!] Connection error: {e}")
        # Release key if it was held
        if button_pressed:
            pyautogui.keyUp(KEY_TO_HOLD)
            button_pressed = False
        
        # Don't exit - wait for user to manually restart
        print("[*] Connection lost. Press Ctrl+C to quit, or restart the script to reconnect.")
        try:
            while True:
                await asyncio.sleep(60)
        except KeyboardInterrupt:
            return


def cleanup_on_exit():
    """Ensure the key is released when the script exits."""
    global button_pressed
    if button_pressed:
        print("Releasing held key...")
        pyautogui.keyUp(KEY_TO_HOLD)
        button_pressed = False


async def main():
    """Main entry point for the application."""
    await connect_and_listen()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n[+] Stopped.")
        cleanup_on_exit()
    except Exception as e:
        print(f"\n[!] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        cleanup_on_exit()
        sys.exit(1)
