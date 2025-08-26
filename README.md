# py_tuya_ble

A standalone Python library for communicating with Tuya Smart devices over Bluetooth Low Energy (BLE).

## Features

- **Pure Python Implementation**: No dependencies on Home Assistant or other home automation frameworks
- **Async/Await Support**: Built on asyncio for efficient concurrent operations
- **Device Management**: Store and manage device credentials securely
- **Datapoint Control**: Read and write device datapoints (switches, sensors, etc.)
- **Auto-reconnection**: Automatic reconnection handling for robust operation
- **Comprehensive Error Handling**: Detailed exceptions for debugging
- **Type Hints**: Full type hint coverage for better IDE support

## Installation

### From PyPI (when published)
```bash
pip install py_tuya_ble
```

### From Source
```bash
git clone https://github.com/yourusername/py_tuya_ble.git
cd py_tuya_ble
pip install -e .
```

### Dependencies
- Python 3.10+
- bleak >= 0.21.0 (BLE communication)
- pycryptodome >= 3.15.0 (encryption)

## Quick Start

### Basic Usage

```python
import asyncio
from py_tuya_ble import TuyaBLEDevice, TuyaBLEDeviceManager
from bleak import BleakScanner

async def main():
    # Create a device manager to store credentials
    manager = TuyaBLEDeviceManager()
    
    # Add your device credentials (obtained from Tuya IoT Platform)
    manager.add_device(
        address="AA:BB:CC:DD:EE:FF",  # Device MAC address
        uuid="your-device-uuid",
        local_key="your-local-key",
        device_id="your-device-id",
        category="your-category",
        product_id="your-product-id",
        device_name="My Tuya Device"
    )
    
    # Scan for BLE devices
    devices = await BleakScanner.discover()
    
    # Find your Tuya device
    for device in devices:
        if device.address == "AA:BB:CC:DD:EE:FF":
            # Create TuyaBLEDevice instance
            tuya_device = TuyaBLEDevice(manager, device)
            
            # Initialize and connect
            await tuya_device.initialize()
            await tuya_device.connect()
            
            # Now you can interact with the device
            print(f"Connected to: {tuya_device.name}")
            print(f"Device version: {tuya_device.device_version}")
            
            # Disconnect when done
            await tuya_device.disconnect()
            break

if __name__ == "__main__":
    asyncio.run(main())
```

### Working with Datapoints

Datapoints are the primary way to interact with Tuya devices. Each datapoint represents a controllable feature or sensor reading.

```python
import asyncio
from py_tuya_ble import TuyaBLEDevice, TuyaBLEDeviceManager, TuyaBLEDataPointType

async def control_device():
    # ... (setup code as above)
    
    # Register a callback for datapoint updates
    def on_datapoint_update(datapoints):
        for dp in datapoints:
            print(f"Datapoint {dp.id} updated: {dp.value}")
    
    tuya_device.register_callback(on_datapoint_update)
    
    # Get or create a datapoint
    # For a switch (boolean)
    switch_dp = tuya_device.datapoints.get_or_create(
        id=1,  # Datapoint ID (device-specific)
        type=TuyaBLEDataPointType.DT_BOOL,
        value=False  # Initial value
    )
    
    # Turn the switch on
    await switch_dp.set_value(True)
    
    # For a brightness control (integer)
    brightness_dp = tuya_device.datapoints.get_or_create(
        id=2,
        type=TuyaBLEDataPointType.DT_VALUE,
        value=50
    )
    
    # Set brightness to 75%
    await brightness_dp.set_value(75)
    
    # Read current values
    print(f"Switch is: {'on' if switch_dp.value else 'off'}")
    print(f"Brightness: {brightness_dp.value}%")
```

### Batch Updates

For efficiency, you can batch multiple datapoint updates:

```python
async def batch_update():
    # Begin batch update
    tuya_device.datapoints.begin_update()
    
    # Update multiple datapoints
    await switch_dp.set_value(True)
    await brightness_dp.set_value(100)
    await color_dp.set_value("FF0000")  # Red color
    
    # Send all updates at once
    await tuya_device.datapoints.end_update()
```

## Device Credentials

To use this library, you need to obtain device credentials from the Tuya IoT Platform:

1. **Register on Tuya IoT Platform**: Create an account at https://iot.tuya.com
2. **Create a Cloud Project**: Set up a new project in the platform
3. **Add Your Device**: Link your physical device to the project
4. **Get Credentials**: Obtain the following for each device:
   - `uuid`: Device UUID
   - `local_key`: Local encryption key
   - `device_id`: Device identifier
   - `category`: Device category (e.g., "light", "switch")
   - `product_id`: Product identifier

### Storing Credentials

The `TuyaBLEDeviceManager` stores credentials in a JSON file by default:

```python
# Default storage location: ~/.py_tuya_ble/devices.json
manager = TuyaBLEDeviceManager()

# Custom storage location
from pathlib import Path
manager = TuyaBLEDeviceManager(storage_path=Path("/path/to/devices.json"))

# List all stored devices
devices = manager.list_devices()
for address, device in devices.items():
    print(f"{address}: {device.device_name}")
```

## Advanced Features

### Connection Callbacks

Monitor connection state changes:

```python
def on_connected():
    print("Device connected!")

def on_disconnected():
    print("Device disconnected!")

# Register callbacks
tuya_device.register_connected_callback(on_connected)
tuya_device.register_disconnected_callback(on_disconnected)
```

### Custom Device Manager

Implement your own device manager for different storage backends:

```python
from py_tuya_ble.manager import TuyaBLEDeviceCredentials

class CustomDeviceManager:
    async def get_device_credentials(
        self, address: str, force_update: bool = False, save_data: bool = False
    ) -> Optional[TuyaBLEDeviceCredentials]:
        # Implement your custom storage logic
        # e.g., fetch from database, cloud service, etc.
        pass
```

### Logging

Enable detailed logging for debugging:

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

# Or configure specific logger
logger = logging.getLogger("py_tuya_ble")
logger.setLevel(logging.DEBUG)
```

## Datapoint Types

The library supports all standard Tuya datapoint types:

| Type | Python Type | Description | Example |
|------|------------|-------------|---------|
| `DT_BOOL` | `bool` | Boolean switch | On/Off switch |
| `DT_VALUE` | `int` | Signed integer | Temperature, brightness |
| `DT_ENUM` | `int` | Enumeration | Mode selection |
| `DT_STRING` | `str` | Text string | Device name |
| `DT_RAW` | `bytes` | Raw bytes | Custom data |
| `DT_BITMAP` | `bytes` | Bit flags | Multiple switches |

## Error Handling

The library provides specific exceptions for different error conditions:

```python
from py_tuya_ble import (
    TuyaBLEError,
    TuyaBLEDeviceError,
    TuyaBLEDataLengthError,
    TuyaBLEDataCRCError,
    TuyaBLEDataFormatError,
    TuyaBLEEnumValueError
)

try:
    await tuya_device.connect()
except TuyaBLEDeviceError as e:
    print(f"Device error: {e}")
except TuyaBLEDataCRCError as e:
    print(f"Data corruption detected: {e}")
except TuyaBLEError as e:
    print(f"General error: {e}")
```

## Protocol Details

This library implements the Tuya BLE protocol v3, which includes:

- **AES Encryption**: All communication is encrypted using AES-128-CBC
- **CRC Verification**: Data integrity checking with CRC16
- **Sequence Numbers**: Packet ordering and response matching
- **MTU Handling**: Automatic packet fragmentation for BLE MTU limits

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

### Development Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/py_tuya_ble.git
cd py_tuya_ble

# Install in development mode with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black py_tuya_ble

# Type checking
mypy py_tuya_ble
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Original implementation based on the Home Assistant Tuya BLE integration
- Thanks to the Tuya Developer Platform for protocol documentation
- Built on top of the excellent [Bleak](https://github.com/hbldh/bleak) BLE library

## Disclaimer

This library is not affiliated with or endorsed by Tuya Inc. It's an independent implementation based on reverse engineering and public documentation.