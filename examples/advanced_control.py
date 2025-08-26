#!/usr/bin/env python3
"""
Advanced example demonstrating complex Tuya BLE device control.

This example shows:
- Batch datapoint updates
- Working with multiple datapoint types
- Error handling and reconnection
- Custom callbacks and event handling
"""

import asyncio
import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime
from py_tuya_ble import (
    TuyaBLEDevice,
    TuyaBLEDeviceManager,
    TuyaBLEDataPointType,
    TuyaBLEDataPoint,
    TuyaBLEError,
    TuyaBLEDeviceError,
)
from bleak import BleakScanner

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Device credentials - replace with your actual values
DEVICE_CONFIG = {
    "address": "AA:BB:CC:DD:EE:FF",
    "uuid": "your-device-uuid",
    "local_key": "your-local-key",
    "device_id": "your-device-id",
    "category": "your-category",
    "product_id": "your-product-id",
    "name": "My Advanced Tuya Device"
}

# Example datapoint configuration (adjust for your device)
DATAPOINTS_CONFIG = {
    1: {"type": TuyaBLEDataPointType.DT_BOOL, "name": "Power Switch"},
    2: {"type": TuyaBLEDataPointType.DT_VALUE, "name": "Brightness", "min": 0, "max": 100},
    3: {"type": TuyaBLEDataPointType.DT_ENUM, "name": "Mode", "values": {0: "Auto", 1: "Manual", 2: "Sleep"}},
    4: {"type": TuyaBLEDataPointType.DT_STRING, "name": "Device Name"},
    5: {"type": TuyaBLEDataPointType.DT_VALUE, "name": "Temperature", "read_only": True},
}


class AdvancedTuyaController:
    """Advanced controller for Tuya BLE devices with comprehensive features."""
    
    def __init__(self, device: TuyaBLEDevice, config: Dict[int, Dict[str, Any]]):
        self.device = device
        self.config = config
        self.datapoints: Dict[int, TuyaBLEDataPoint] = {}
        self.last_update_time: Dict[int, datetime] = {}
        self.update_history: list = []
        self.connection_state = False
        self.reconnect_task: Optional[asyncio.Task] = None
        
        # Register callbacks
        self.device.register_callback(self.on_datapoint_update)
        self.device.register_connected_callback(self.on_connected)
        self.device.register_disconnected_callback(self.on_disconnected)
    
    async def initialize(self):
        """Initialize all configured datapoints."""
        logger.info("Initializing datapoints...")
        
        for dp_id, dp_config in self.config.items():
            dp_type = dp_config["type"]
            name = dp_config.get("name", f"Datapoint {dp_id}")
            
            # Set initial values based on type
            initial_value = None
            if dp_type == TuyaBLEDataPointType.DT_BOOL:
                initial_value = False
            elif dp_type == TuyaBLEDataPointType.DT_VALUE:
                initial_value = dp_config.get("min", 0)
            elif dp_type == TuyaBLEDataPointType.DT_ENUM:
                initial_value = 0
            elif dp_type == TuyaBLEDataPointType.DT_STRING:
                initial_value = ""
            elif dp_type in [TuyaBLEDataPointType.DT_RAW, TuyaBLEDataPointType.DT_BITMAP]:
                initial_value = b""
            
            dp = self.device.datapoints.get_or_create(
                id=dp_id,
                type=dp_type,
                value=initial_value
            )
            self.datapoints[dp_id] = dp
            logger.info(f"  Initialized {name} (DP {dp_id}, type: {dp_type.name})")
    
    def on_connected(self):
        """Handle device connection."""
        logger.info("Device connected!")
        self.connection_state = True
        
        # Cancel reconnection task if running
        if self.reconnect_task and not self.reconnect_task.done():
            self.reconnect_task.cancel()
    
    def on_disconnected(self):
        """Handle device disconnection."""
        logger.warning("Device disconnected!")
        self.connection_state = False
        
        # Start reconnection task
        if not self.reconnect_task or self.reconnect_task.done():
            self.reconnect_task = asyncio.create_task(self.auto_reconnect())
    
    def on_datapoint_update(self, datapoints: list[TuyaBLEDataPoint]):
        """Handle datapoint updates from device."""
        for dp in datapoints:
            dp_config = self.config.get(dp.id, {})
            name = dp_config.get("name", f"Datapoint {dp.id}")
            
            # Record update time
            self.last_update_time[dp.id] = datetime.now()
            
            # Add to history
            update_record = {
                "timestamp": datetime.now().isoformat(),
                "dp_id": dp.id,
                "name": name,
                "value": dp.value,
                "type": dp.type.name
            }
            self.update_history.append(update_record)
            
            # Limit history size
            if len(self.update_history) > 100:
                self.update_history.pop(0)
            
            # Log the update
            logger.info(f"📊 {name} (DP {dp.id}) updated: {dp.value}")
            
            # Special handling for certain types
            if dp.type == TuyaBLEDataPointType.DT_ENUM and dp.id in self.config:
                values_map = self.config[dp.id].get("values", {})
                if dp.value in values_map:
                    logger.info(f"   Mode: {values_map[dp.value]}")
    
    async def auto_reconnect(self):
        """Automatically reconnect to device."""
        retry_count = 0
        max_retries = 10
        base_delay = 5  # seconds
        
        while retry_count < max_retries and not self.connection_state:
            retry_count += 1
            delay = base_delay * (2 ** min(retry_count - 1, 3))  # Exponential backoff, capped
            
            logger.info(f"Reconnection attempt {retry_count}/{max_retries} in {delay} seconds...")
            await asyncio.sleep(delay)
            
            try:
                await self.device.connect()
                logger.info("Reconnection successful!")
                break
            except Exception as e:
                logger.error(f"Reconnection failed: {e}")
        
        if retry_count >= max_retries:
            logger.error("Max reconnection attempts reached. Please check device.")
    
    async def set_datapoint_safe(self, dp_id: int, value: Any) -> bool:
        """Safely set a datapoint value with validation."""
        if dp_id not in self.datapoints:
            logger.error(f"Datapoint {dp_id} not found")
            return False
        
        dp_config = self.config.get(dp_id, {})
        
        # Check if read-only
        if dp_config.get("read_only", False):
            logger.warning(f"Datapoint {dp_id} is read-only")
            return False
        
        # Validate value based on type
        dp = self.datapoints[dp_id]
        
        try:
            if dp.type == TuyaBLEDataPointType.DT_VALUE:
                # Check min/max bounds
                min_val = dp_config.get("min")
                max_val = dp_config.get("max")
                if min_val is not None and value < min_val:
                    logger.warning(f"Value {value} below minimum {min_val}")
                    value = min_val
                if max_val is not None and value > max_val:
                    logger.warning(f"Value {value} above maximum {max_val}")
                    value = max_val
            
            elif dp.type == TuyaBLEDataPointType.DT_ENUM:
                # Check valid enum values
                valid_values = dp_config.get("values", {})
                if valid_values and value not in valid_values:
                    logger.error(f"Invalid enum value {value}. Valid: {list(valid_values.keys())}")
                    return False
            
            # Set the value
            logger.info(f"Setting {dp_config.get('name', f'DP {dp_id}')} to {value}")
            await dp.set_value(value)
            return True
            
        except Exception as e:
            logger.error(f"Error setting datapoint {dp_id}: {e}")
            return False
    
    async def batch_update(self, updates: Dict[int, Any]):
        """Perform batch update of multiple datapoints."""
        logger.info(f"Performing batch update of {len(updates)} datapoints...")
        
        # Begin batch
        self.device.datapoints.begin_update()
        
        success_count = 0
        for dp_id, value in updates.items():
            if await self.set_datapoint_safe(dp_id, value):
                success_count += 1
        
        # Send batch
        await self.device.datapoints.end_update()
        
        logger.info(f"Batch update complete: {success_count}/{len(updates)} successful")
        return success_count == len(updates)
    
    def get_status_report(self) -> Dict[str, Any]:
        """Generate a comprehensive status report."""
        report = {
            "connection_state": self.connection_state,
            "device_info": {
                "name": self.device.name,
                "address": self.device.address,
                "rssi": self.device.rssi,
                "version": self.device.device_version,
                "protocol": self.device.protocol_version,
            },
            "datapoints": {},
            "last_updates": {},
            "recent_history": self.update_history[-10:] if self.update_history else []
        }
        
        for dp_id, dp in self.datapoints.items():
            dp_config = self.config.get(dp_id, {})
            name = dp_config.get("name", f"Datapoint {dp_id}")
            
            report["datapoints"][name] = {
                "id": dp_id,
                "type": dp.type.name,
                "value": dp.value,
                "last_update": self.last_update_time.get(dp_id, "Never").isoformat() 
                              if dp_id in self.last_update_time else "Never"
            }
        
        return report
    
    async def save_state(self, filename: str):
        """Save current device state to file."""
        state = self.get_status_report()
        with open(filename, 'w') as f:
            json.dump(state, f, indent=2, default=str)
        logger.info(f"State saved to {filename}")
    
    async def restore_state(self, filename: str):
        """Restore device state from file."""
        try:
            with open(filename, 'r') as f:
                state = json.load(f)
            
            updates = {}
            for name, dp_info in state.get("datapoints", {}).items():
                dp_id = dp_info["id"]
                value = dp_info["value"]
                
                # Skip read-only datapoints
                if self.config.get(dp_id, {}).get("read_only", False):
                    continue
                
                updates[dp_id] = value
            
            if updates:
                await self.batch_update(updates)
                logger.info(f"State restored from {filename}")
            
        except Exception as e:
            logger.error(f"Failed to restore state: {e}")


async def demo_advanced_features(controller: AdvancedTuyaController):
    """Demonstrate advanced controller features."""
    
    print("\n=== Advanced Feature Demo ===\n")
    
    # 1. Status Report
    print("1. Getting status report...")
    report = controller.get_status_report()
    print(json.dumps(report, indent=2, default=str))
    
    await asyncio.sleep(2)
    
    # 2. Individual control
    print("\n2. Individual datapoint control...")
    if 1 in controller.datapoints:  # Power switch
        await controller.set_datapoint_safe(1, True)
        await asyncio.sleep(1)
    
    if 2 in controller.datapoints:  # Brightness
        for brightness in [25, 50, 75, 100]:
            print(f"   Setting brightness to {brightness}%")
            await controller.set_datapoint_safe(2, brightness)
            await asyncio.sleep(1)
    
    # 3. Batch update
    print("\n3. Batch update demo...")
    batch_updates = {
        1: False,  # Power off
        2: 50,     # Brightness 50%
        3: 1,      # Mode Manual
    }
    await controller.batch_update(batch_updates)
    await asyncio.sleep(2)
    
    # 4. Save state
    print("\n4. Saving device state...")
    await controller.save_state("device_state.json")
    
    # 5. Modify and restore
    print("\n5. Modifying state...")
    await controller.set_datapoint_safe(1, True)
    await controller.set_datapoint_safe(2, 100)
    await asyncio.sleep(2)
    
    print("   Restoring saved state...")
    await controller.restore_state("device_state.json")
    await asyncio.sleep(2)


async def main():
    """Main function for advanced control example."""
    
    print("=== Tuya BLE Advanced Control Example ===\n")
    
    # Setup
    manager = TuyaBLEDeviceManager()
    manager.add_device(
        address=DEVICE_CONFIG["address"],
        uuid=DEVICE_CONFIG["uuid"],
        local_key=DEVICE_CONFIG["local_key"],
        device_id=DEVICE_CONFIG["device_id"],
        category=DEVICE_CONFIG["category"],
        product_id=DEVICE_CONFIG["product_id"],
        device_name=DEVICE_CONFIG["name"]
    )
    
    # Scan for device
    print("Scanning for device...")
    devices = await BleakScanner.discover(timeout=5.0)
    
    target_device = None
    for device in devices:
        if device.address.upper() == DEVICE_CONFIG["address"].upper():
            target_device = device
            print(f"Found device: {device.name} at {device.address}")
            break
    
    if not target_device:
        print(f"ERROR: Device {DEVICE_CONFIG['address']} not found")
        return
    
    # Create device and controller
    tuya_device = TuyaBLEDevice(manager, target_device)
    await tuya_device.initialize()
    
    controller = AdvancedTuyaController(tuya_device, DATAPOINTS_CONFIG)
    await controller.initialize()
    
    try:
        # Connect
        print("\nConnecting to device...")
        await tuya_device.connect()
        print("Connected successfully!")
        
        # Request status
        await tuya_device.update()
        await asyncio.sleep(2)
        
        # Run demo
        await demo_advanced_features(controller)
        
        # Interactive mode
        print("\n=== Interactive Mode ===")
        print("Commands:")
        print("  status - Show device status")
        print("  set <dp_id> <value> - Set datapoint value")
        print("  batch - Perform batch update")
        print("  save - Save current state")
        print("  restore - Restore saved state")
        print("  history - Show update history")
        print("  quit - Exit")
        
        while True:
            try:
                command = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None, input, "\nCommand: "
                    ),
                    timeout=60.0
                )
                
                parts = command.split()
                if not parts:
                    continue
                
                cmd = parts[0].lower()
                
                if cmd == "quit":
                    break
                elif cmd == "status":
                    report = controller.get_status_report()
                    print(json.dumps(report, indent=2, default=str))
                elif cmd == "set" and len(parts) >= 3:
                    dp_id = int(parts[1])
                    value = parts[2]
                    # Try to parse value
                    try:
                        value = json.loads(value)
                    except:
                        pass
                    await controller.set_datapoint_safe(dp_id, value)
                elif cmd == "batch":
                    print("Enter updates as JSON dict:")
                    updates_str = input()
                    updates = json.loads(updates_str)
                    await controller.batch_update(updates)
                elif cmd == "save":
                    await controller.save_state("device_state.json")
                elif cmd == "restore":
                    await controller.restore_state("device_state.json")
                elif cmd == "history":
                    for record in controller.update_history[-10:]:
                        print(f"{record['timestamp']}: {record['name']} = {record['value']}")
                else:
                    print("Unknown command or invalid syntax")
                
            except asyncio.TimeoutError:
                print("\nTimeout - exiting")
                break
            except Exception as e:
                print(f"Error: {e}")
        
    except TuyaBLEDeviceError as e:
        logger.error(f"Device error: {e}")
    except TuyaBLEError as e:
        logger.error(f"Tuya BLE error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
    finally:
        print("\nDisconnecting...")
        await tuya_device.disconnect()
        print("Disconnected")
    
    print("\n=== Example Complete ===")


if __name__ == "__main__":
    asyncio.run(main())