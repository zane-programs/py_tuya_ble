#!/usr/bin/env python3
"""
Basic example demonstrating how to connect to a Tuya BLE device.

This example shows:
- Setting up device credentials
- Scanning for BLE devices
- Connecting to a specific device
- Reading device information
"""

import asyncio
import logging
from pathlib import Path
from py_tuya_ble import TuyaBLEDevice, TuyaBLEDeviceManager
from bleak import BleakScanner

# Enable debug logging to see what's happening
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Device credentials - replace with your actual values
DEVICE_ADDRESS = ""
DEVICE_UUID = ""
DEVICE_LOCAL_KEY = ""
DEVICE_ID = ""
DEVICE_CATEGORY = ""
DEVICE_PRODUCT_ID = ""


async def main():
    """Main function demonstrating basic connection."""
    
    print("=== Tuya BLE Basic Connection Example ===\n")
    
    # Step 1: Create a device manager
    print("1. Setting up device manager...")
    manager = TuyaBLEDeviceManager()
    
    # Step 2: Add device credentials
    print("2. Adding device credentials...")
    device_creds = manager.add_device(
        address=DEVICE_ADDRESS,
        uuid=DEVICE_UUID,
        local_key=DEVICE_LOCAL_KEY,
        device_id=DEVICE_ID,
        category=DEVICE_CATEGORY,
        product_id=DEVICE_PRODUCT_ID,
        device_name="My Tuya Device"
    )
    print(f"   Added device: {device_creds.device_name}")
    
    # Step 3: Scan for BLE devices
    print("\n3. Scanning for BLE devices...")
    devices = await BleakScanner.discover(timeout=5.0)
    print(f"   Found {len(devices)} BLE devices")
    for device in devices:
        print(f"   - {device.name} ({device.address})")
    
    # Find our Tuya device
    target_device = None
    for device in devices:
        if device.address.upper() == DEVICE_ADDRESS.upper():
            target_device = device
            print(f"   Found target device: {device.name} at {device.address}")
            break
    
    if not target_device:
        print(f"   ERROR: Could not find device with address {DEVICE_ADDRESS}")
        print("   Make sure the device is powered on and in range")
        return
    
    # Step 4: Create TuyaBLEDevice instance
    print("\n4. Creating Tuya BLE device instance...")
    tuya_device = TuyaBLEDevice(manager, target_device)
    
    # Step 5: Initialize the device
    print("5. Initializing device...")
    await tuya_device.initialize()
    
    # Step 6: Connect to the device
    print("6. Connecting to device...")
    try:
        await tuya_device.connect()
        print("   Successfully connected!")
        
        # Step 7: Read device information
        print("\n7. Device Information:")
        print(f"   Name: {tuya_device.name}")
        print(f"   Address: {tuya_device.address}")
        print(f"   RSSI: {tuya_device.rssi} dBm")
        print(f"   Device Version: {tuya_device.device_version}")
        print(f"   Hardware Version: {tuya_device.hardware_version}")
        print(f"   Protocol Version: {tuya_device.protocol_version}")
        print(f"   Is Paired: {tuya_device.is_paired}")
        print(f"   Is Connected: {tuya_device.is_connected}")
        
        # Wait a moment to ensure stable connection
        await asyncio.sleep(2)
        
        # Step 8: Request device status update
        print("\n8. Requesting device status...")
        await tuya_device.update()
        print("   Status update requested")
        
        # Wait for any datapoint updates
        await asyncio.sleep(2)
        
        # Step 9: Check available datapoints
        print("\n9. Available Datapoints:")
        if len(tuya_device.datapoints) > 0:
            for dp_id in range(256):  # Check common datapoint IDs
                dp = tuya_device.datapoints[dp_id]
                if dp:
                    print(f"   Datapoint {dp.id}: {dp.type.name} = {dp.value}")
        else:
            print("   No datapoints discovered yet")
        
    except Exception as e:
        print(f"   Connection failed: {e}")
    finally:
        # Step 10: Disconnect
        print("\n10. Disconnecting...")
        await tuya_device.disconnect()
        print("    Disconnected")
    
    print("\n=== Example Complete ===")


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())