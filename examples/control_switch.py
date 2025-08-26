#!/usr/bin/env python3
"""
Example demonstrating how to control a Tuya BLE switch device.

This example shows:
- Connecting to a switch device
- Reading the current switch state
- Toggling the switch on and off
- Listening for state changes
"""

import asyncio
import logging
from py_tuya_ble import (
    TuyaBLEDevice,
    TuyaBLEDeviceManager,
    TuyaBLEDataPointType,
)
from bleak import BleakScanner

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Device credentials - replace with your actual values
DEVICE_ADDRESS = "AA:BB:CC:DD:EE:FF"
DEVICE_UUID = "your-device-uuid"
DEVICE_LOCAL_KEY = "your-local-key"
DEVICE_ID = "your-device-id"
DEVICE_CATEGORY = "switch"  # or whatever your device category is
DEVICE_PRODUCT_ID = "your-product-id"

# Common datapoint IDs for switches (may vary by device)
SWITCH_DP_ID = 1  # Main switch datapoint


class TuyaSwitchController:
    """Controller class for Tuya switch devices."""
    
    def __init__(self, device: TuyaBLEDevice):
        self.device = device
        self.switch_dp = None
        
        # Register callback for datapoint updates
        self.device.register_callback(self.on_datapoint_update)
    
    def on_datapoint_update(self, datapoints):
        """Handle datapoint updates from the device."""
        for dp in datapoints:
            print(f"Datapoint {dp.id} updated: {dp.value}")
            if dp.id == SWITCH_DP_ID:
                state = "ON" if dp.value else "OFF"
                print(f">>> Switch is now {state}")
    
    async def setup(self):
        """Setup the switch datapoint."""
        # Get or create the switch datapoint
        self.switch_dp = self.device.datapoints.get_or_create(
            id=SWITCH_DP_ID,
            type=TuyaBLEDataPointType.DT_BOOL,
            value=False
        )
        print(f"Switch datapoint initialized")
    
    async def get_state(self) -> bool:
        """Get the current switch state."""
        if self.switch_dp:
            return bool(self.switch_dp.value)
        return False
    
    async def turn_on(self):
        """Turn the switch on."""
        if self.switch_dp:
            print("Turning switch ON...")
            await self.switch_dp.set_value(True)
    
    async def turn_off(self):
        """Turn the switch off."""
        if self.switch_dp:
            print("Turning switch OFF...")
            await self.switch_dp.set_value(False)
    
    async def toggle(self):
        """Toggle the switch state."""
        current = await self.get_state()
        new_state = not current
        print(f"Toggling switch from {'ON' if current else 'OFF'} to {'ON' if new_state else 'OFF'}...")
        await self.switch_dp.set_value(new_state)


async def main():
    """Main function demonstrating switch control."""
    
    print("=== Tuya BLE Switch Control Example ===\n")
    
    # Setup device manager and credentials
    manager = TuyaBLEDeviceManager()
    manager.add_device(
        address=DEVICE_ADDRESS,
        uuid=DEVICE_UUID,
        local_key=DEVICE_LOCAL_KEY,
        device_id=DEVICE_ID,
        category=DEVICE_CATEGORY,
        product_id=DEVICE_PRODUCT_ID,
        device_name="My Tuya Switch"
    )
    
    # Scan for the device
    print("Scanning for device...")
    devices = await BleakScanner.discover(timeout=5.0)
    
    target_device = None
    for device in devices:
        if device.address.upper() == DEVICE_ADDRESS.upper():
            target_device = device
            print(f"Found device: {device.name} at {device.address}")
            break
    
    if not target_device:
        print(f"ERROR: Device {DEVICE_ADDRESS} not found")
        return
    
    # Create and connect to device
    tuya_device = TuyaBLEDevice(manager, target_device)
    await tuya_device.initialize()
    
    try:
        print("\nConnecting to device...")
        await tuya_device.connect()
        print("Connected successfully!")
        
        # Create switch controller
        controller = TuyaSwitchController(tuya_device)
        await controller.setup()
        
        # Request initial status
        print("\nRequesting device status...")
        await tuya_device.update()
        await asyncio.sleep(2)
        
        # Get current state
        current_state = await controller.get_state()
        print(f"\nCurrent switch state: {'ON' if current_state else 'OFF'}")
        
        # Demonstrate control
        print("\n--- Switch Control Demo ---")
        
        # Turn on
        await controller.turn_on()
        await asyncio.sleep(2)
        
        # Turn off
        await controller.turn_off()
        await asyncio.sleep(2)
        
        # Toggle a few times
        for i in range(3):
            print(f"\nToggle #{i+1}")
            await controller.toggle()
            await asyncio.sleep(2)
        
        # Interactive control
        print("\n--- Interactive Control ---")
        print("Commands: 'on', 'off', 'toggle', 'status', 'quit'")
        
        while True:
            try:
                # Get user input with timeout
                command = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None, input, "Enter command: "
                    ),
                    timeout=30.0
                )
                
                if command.lower() == 'quit':
                    break
                elif command.lower() == 'on':
                    await controller.turn_on()
                elif command.lower() == 'off':
                    await controller.turn_off()
                elif command.lower() == 'toggle':
                    await controller.toggle()
                elif command.lower() == 'status':
                    state = await controller.get_state()
                    print(f"Switch is {'ON' if state else 'OFF'}")
                else:
                    print("Unknown command. Use: on, off, toggle, status, quit")
                
                await asyncio.sleep(1)
                
            except asyncio.TimeoutError:
                print("\nTimeout - exiting interactive mode")
                break
            except Exception as e:
                print(f"Error: {e}")
                break
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        print("\nDisconnecting...")
        await tuya_device.disconnect()
        print("Disconnected")
    
    print("\n=== Example Complete ===")


if __name__ == "__main__":
    asyncio.run(main())