#!/usr/bin/env python3
"""
Anytone PTT Bluetooth Controller
Uses bleak library to connect to Anytone/ELET PTT buttons and trigger keyboard events.
This script holds down a key (default: Ctrl) while the PTT button is pressed,
and releases it when the button is released - perfect for push-to-talk applications.

Configuration is stored in config.ini for easy customization.
The script continuously scans for the PTT device and automatically reconnects if connection is lost.
"""
import asyncio
import sys
import os
from pathlib import Path
from configparser import ConfigParser
from bleak import BleakClient, BleakScanner
import pyautogui

# Configuration defaults
DEFAULT_CONFIG = {
    'PTT': {
        'mac_address': '',
        'key_to_hold': 'ctrl'
    },
    'Connection': {
        'scan_interval': '5',
        'reconnect_delay': '3'
    },
    'Bluetooth': {
        'ptt_uuid': '0000ff02-0000-1000-8000-00805f9b34fb'
    }
}

# Global state
button_pressed = False
should_run = True
config = None
PTT_MAC = None


def load_config():
    """
    Load configuration from config.ini file.
    Creates default config if file doesn't exist.
    
    Returns:
        ConfigParser: Configuration object
    """
    script_dir = Path(__file__).parent
    config_file = script_dir / 'config.ini'
    
    cfg = ConfigParser()
    
    # If config file doesn't exist, create it with defaults
    if not config_file.exists():
        print(f"[*] Creating default config file: {config_file}")
        cfg.read_dict(DEFAULT_CONFIG)
        with open(config_file, 'w') as f:
            f.write("# Anytone PTT Configuration File\n")
            f.write("# Edit this file to customize your PTT settings\n\n")
            cfg.write(f)
        print("[+] Config file created. Edit config.ini to set your device MAC address.")
    else:
        cfg.read(config_file)
    
    return cfg


def save_mac_to_config(mac_address):
    """
    Save the MAC address to config file for future use.
    
    Args:
        mac_address: MAC address to save
    """
    global config
    script_dir = Path(__file__).parent
    config_file = script_dir / 'config.ini'
    
    config.set('PTT', 'mac_address', mac_address)
    
    with open(config_file, 'w') as f:
        f.write("# Anytone PTT Configuration File\n")
        f.write("# Edit this file to customize your PTT settings\n\n")
        config.write(f)
    
    print(f"[+] Saved MAC address to config.ini: {mac_address}")


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
    global button_pressed, config
    
    # Validate data
    if not data or len(data) < 5:
        return
    
    # Decode the message as ASCII
    try:
        message = data.decode('ascii')
    except UnicodeDecodeError:
        message = data.hex()
    
    print(f"Received: {message}")
    
    key_to_hold = config.get('PTT', 'key_to_hold', fallback='ctrl')
    
    # Handle button press
    if message.startswith("ELET1"):
        if not button_pressed:
            print(f"-> Button PRESSED - holding '{key_to_hold}'")
            pyautogui.keyDown(key_to_hold)
            button_pressed = True
    
    # Handle button release
    elif message.startswith("ELET2"):
        if button_pressed:
            print(f"-> Button RELEASED - releasing '{key_to_hold}'")
            pyautogui.keyUp(key_to_hold)
            button_pressed = False
    
    # Battery status messages are ignored
    elif message.startswith("BATT"):
        pass


async def find_ptt_device():
    """
    Scan for ELET-PTT devices and return the MAC address.
    
    If PTT_MAC is already set (from config), validates it exists.
    If multiple devices are found, prompts user to choose and saves selection.
    
    Returns:
        str: MAC address of device, or None if not found
    """
    global PTT_MAC
    
    # If MAC is already set, just verify it's available
    if PTT_MAC:
        devices = await BleakScanner.discover(timeout=3.0)
        for device in devices:
            if device.address.upper() == PTT_MAC.upper():
                return PTT_MAC
        print(f"[!] Configured device {PTT_MAC} not found")
        return None
    
    # Scan for ELET-PTT devices
    print("[*] Scanning for ELET-PTT devices...")
    devices = await BleakScanner.discover(timeout=5.0)
    
    # Filter for ELET-PTT devices
    ptt_devices = []
    for device in devices:
        if device.name and "ELET-PTT" in device.name:
            ptt_devices.append(device)
            print(f"    Found: {device.address} - {device.name}")
    
    if not ptt_devices:
        return None
    
    # Auto-select if only one device
    if len(ptt_devices) == 1:
        selected_mac = ptt_devices[0].address
        print(f"[+] Auto-selected: {selected_mac}")
        PTT_MAC = selected_mac
        save_mac_to_config(selected_mac)
        return selected_mac
    
    # Multiple devices found - prompt user to choose
    print("\n[*] Multiple devices found. Please choose:")
    for i, device in enumerate(ptt_devices):
        print(f"    {i+1}. {device.address} - {device.name}")
    
    try:
        choice = input("Enter number: ")
        idx = int(choice) - 1
        if 0 <= idx < len(ptt_devices):
            selected_mac = ptt_devices[idx].address
            PTT_MAC = selected_mac
            save_mac_to_config(selected_mac)
            return selected_mac
        else:
            print("[!] Invalid choice")
            return None
    except (ValueError, KeyboardInterrupt):
        print("\n[!] Selection cancelled")
        return None


async def connect_and_listen(mac_address):
    """
    Connect to the PTT device and listen for button press notifications.
    
    Args:
        mac_address: MAC address of the device to connect to
        
    Returns:
        bool: True if connection was successful, False if error
    """
    global button_pressed, config
    
    print(f"[*] Connecting to {mac_address}...")
    
    ptt_uuid = config.get('Bluetooth', 'ptt_uuid', fallback='0000ff02-0000-1000-8000-00805f9b34fb')
    key_to_hold = config.get('PTT', 'key_to_hold', fallback='ctrl')
    
    try:
        async with BleakClient(mac_address, timeout=15.0) as client:
            if not client.is_connected:
                print("[!] Failed to connect")
                return False
            
            print("[+] Connected successfully!")
            print(f"[*] PTT will hold '{key_to_hold}' key while pressed")
            print("[*] Keep iaxRPT window focused for PTT to work")
            
            # Subscribe to notifications
            await client.start_notify(ptt_uuid, handle_notify)
            print("[*] Listening for button presses...\n")
            
            # Keep listening until connection drops or user interrupts
            try:
                while should_run:
                    await asyncio.sleep(1)
                    # Check if still connected
                    if not client.is_connected:
                        print("[!] Connection lost")
                        break
                        
            except asyncio.CancelledError:
                # Clean shutdown
                if button_pressed:
                    print("[*] Releasing held key...")
                    pyautogui.keyUp(key_to_hold)
                    button_pressed = False
                raise
            
            # Stop notifications before disconnect
            try:
                await client.stop_notify(ptt_uuid)
            except:
                pass
            
            return True
                
    except Exception as e:
        print(f"[!] Connection error: {e}")
        # Release key if it was held
        if button_pressed:
            key_to_hold = config.get('PTT', 'key_to_hold', fallback='ctrl')
            pyautogui.keyUp(key_to_hold)
            button_pressed = False
        return False


async def main():
    """
    Main loop - continuously scans for PTT device and maintains connection.
    """
    global should_run, config, PTT_MAC
    
    # Load configuration
    config = load_config()
    
    # Get MAC address from config
    mac_from_config = config.get('PTT', 'mac_address', fallback='').strip()
    if mac_from_config:
        PTT_MAC = mac_from_config
        print(f"[+] Using MAC address from config: {PTT_MAC}")
    
    # Get timing settings
    scan_interval = config.getint('Connection', 'scan_interval', fallback=5)
    reconnect_delay = config.getint('Connection', 'reconnect_delay', fallback=3)
    
    print("=== Anytone PTT Bluetooth Controller ===")
    print("[*] Press Ctrl+C to quit\n")
    
    while should_run:
        try:
            # Find the PTT device
            mac_address = await find_ptt_device()
            
            if mac_address:
                # Try to connect and listen
                await connect_and_listen(mac_address)
                
                # If we get here, connection was lost
                if should_run:
                    print(f"[*] Will retry connection in {reconnect_delay} seconds...")
                    await asyncio.sleep(reconnect_delay)
            else:
                # Device not found
                print(f"[!] No ELET-PTT device found")
                print(f"[*] Will scan again in {scan_interval} seconds...")
                print("[*] Make sure PTT is powered on and press button to wake it\n")
                await asyncio.sleep(scan_interval)
                
        except asyncio.CancelledError:
            # User pressed Ctrl+C
            should_run = False
            break
        except Exception as e:
            print(f"[!] Unexpected error: {e}")
            if should_run:
                print(f"[*] Will retry in {reconnect_delay} seconds...")
                await asyncio.sleep(reconnect_delay)


def cleanup_on_exit():
    """Ensure the key is released when the script exits."""
    global button_pressed, config
    if button_pressed:
        print("[*] Releasing held key...")
        if config:
            key_to_hold = config.get('PTT', 'key_to_hold', fallback='ctrl')
        else:
            key_to_hold = 'ctrl'
        pyautogui.keyUp(key_to_hold)
        button_pressed = False


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n[+] Stopped by user")
        cleanup_on_exit()
    except Exception as e:
        print(f"\n[!] Fatal error: {e}")
        import traceback
        traceback.print_exc()
        cleanup_on_exit()
        sys.exit(1)
