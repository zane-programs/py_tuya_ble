#!/usr/bin/env python3
"""
Example demonstrating how to scan for Tuya BLE devices.

This example shows:
- Scanning for all BLE devices
- Identifying potential Tuya devices
- Extracting advertisement data
- Continuous scanning with callbacks
"""

import asyncio
import logging
from typing import Dict, Set
from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Tuya BLE service UUID
TUYA_SERVICE_UUID = "0000a201-0000-1000-8000-00805f9b34fb"
TUYA_MANUFACTURER_ID = 0x07D0


class TuyaBLEScanner:
    """Scanner for Tuya BLE devices."""
    
    def __init__(self):
        self.discovered_devices: Dict[str, BLEDevice] = {}
        self.tuya_devices: Set[str] = set()
        self.scanner = None
    
    def is_tuya_device(self, device: BLEDevice, adv_data: AdvertisementData) -> bool:
        """Check if a device is likely a Tuya device."""
        # Check for Tuya service UUID
        if adv_data.service_uuids:
            if TUYA_SERVICE_UUID in adv_data.service_uuids:
                return True
        
        # Check for Tuya service data
        if adv_data.service_data:
            if TUYA_SERVICE_UUID in adv_data.service_data:
                return True
        
        # Check for Tuya manufacturer data
        if adv_data.manufacturer_data:
            if TUYA_MANUFACTURER_ID in adv_data.manufacturer_data:
                return True
        
        # Check device name patterns (common Tuya device name prefixes)
        if device.name:
            name_lower = device.name.lower()
            tuya_patterns = ['tuya', 'ty', 'smart', 'ble']
            for pattern in tuya_patterns:
                if pattern in name_lower:
                    return True
        
        return False
    
    def decode_tuya_advertisement(self, adv_data: AdvertisementData) -> Dict:
        """Decode Tuya-specific advertisement data."""
        info = {}
        
        # Extract service data
        if adv_data.service_data:
            service_data = adv_data.service_data.get(TUYA_SERVICE_UUID)
            if service_data:
                info['service_data'] = service_data.hex()
                if len(service_data) > 0:
                    info['service_data_type'] = service_data[0]
        
        # Extract manufacturer data
        if adv_data.manufacturer_data:
            mfr_data = adv_data.manufacturer_data.get(TUYA_MANUFACTURER_ID)
            if mfr_data:
                info['manufacturer_data'] = mfr_data.hex()
                if len(mfr_data) > 1:
                    info['is_bound'] = (mfr_data[0] & 0x80) != 0
                    info['protocol_version'] = mfr_data[1]
        
        return info
    
    def on_device_discovered(self, device: BLEDevice, adv_data: AdvertisementData):
        """Callback when a device is discovered."""
        # Update device list
        self.discovered_devices[device.address] = device
        
        # Check if it's a Tuya device
        if self.is_tuya_device(device, adv_data):
            is_new = device.address not in self.tuya_devices
            self.tuya_devices.add(device.address)
            
            if is_new:
                print(f"\n{'='*60}")
                print(f"TUYA DEVICE DISCOVERED!")
                print(f"{'='*60}")
            else:
                print(f"\n{'='*60}")
                print(f"TUYA DEVICE UPDATE")
                print(f"{'='*60}")
            
            print(f"Address: {device.address}")
            print(f"Name: {device.name or 'Unknown'}")
            print(f"RSSI: {adv_data.rssi} dBm")
            
            # Decode Tuya-specific data
            tuya_info = self.decode_tuya_advertisement(adv_data)
            if tuya_info:
                print("\nTuya-specific data:")
                for key, value in tuya_info.items():
                    print(f"  {key}: {value}")
            
            # Show all service UUIDs
            if adv_data.service_uuids:
                print(f"\nService UUIDs:")
                for uuid in adv_data.service_uuids:
                    print(f"  {uuid}")
            
            print(f"{'='*60}\n")
        else:
            # Non-Tuya device
            print(f".", end="", flush=True)
    
    async def scan_once(self, duration: float = 10.0):
        """Perform a single scan for devices."""
        print(f"\n=== Scanning for {duration} seconds ===\n")
        
        devices = await BleakScanner.discover(
            timeout=duration,
            return_adv=True
        )
        
        print(f"\n\n=== Scan Results ===")
        print(f"Total devices found: {len(devices)}")
        
        tuya_count = 0
        for address, (device, adv_data) in devices.items():
            if self.is_tuya_device(device, adv_data):
                tuya_count += 1
                print(f"\nTuya Device #{tuya_count}:")
                print(f"  Address: {address}")
                print(f"  Name: {device.name or 'Unknown'}")
                print(f"  RSSI: {adv_data.rssi} dBm")
                
                tuya_info = self.decode_tuya_advertisement(adv_data)
                if tuya_info:
                    for key, value in tuya_info.items():
                        print(f"  {key}: {value}")
        
        if tuya_count == 0:
            print("\nNo Tuya devices found.")
            print("\nAll discovered devices:")
            for address, (device, adv_data) in devices.items():
                print(f"  {address}: {device.name or 'Unknown'} (RSSI: {adv_data.rssi})")
    
    async def scan_continuous(self, duration: float = 30.0):
        """Continuously scan for devices with live updates."""
        print(f"\n=== Continuous Scanning for {duration} seconds ===")
        print("Dots (.) indicate non-Tuya devices\n")
        
        self.scanner = BleakScanner(
            detection_callback=self.on_device_discovered
        )
        
        await self.scanner.start()
        await asyncio.sleep(duration)
        await self.scanner.stop()
        
        print(f"\n\n=== Final Summary ===")
        print(f"Total devices discovered: {len(self.discovered_devices)}")
        print(f"Tuya devices found: {len(self.tuya_devices)}")
        
        if self.tuya_devices:
            print("\nTuya device addresses:")
            for address in self.tuya_devices:
                device = self.discovered_devices[address]
                print(f"  {address}: {device.name or 'Unknown'}")


async def main():
    """Main function demonstrating device scanning."""
    
    print("=== Tuya BLE Device Scanner ===\n")
    print("This tool will scan for Tuya BLE devices in range.\n")
    
    scanner = TuyaBLEScanner()
    
    while True:
        print("\nSelect scan mode:")
        print("1. Quick scan (10 seconds)")
        print("2. Long scan (30 seconds)")
        print("3. Continuous scan with live updates (30 seconds)")
        print("4. Custom duration scan")
        print("5. Exit")
        
        try:
            choice = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None, input, "\nEnter choice (1-5): "
                ),
                timeout=60.0
            )
            
            if choice == '1':
                await scanner.scan_once(10.0)
            elif choice == '2':
                await scanner.scan_once(30.0)
            elif choice == '3':
                await scanner.scan_continuous(30.0)
            elif choice == '4':
                duration_str = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None, input, "Enter scan duration in seconds: "
                    ),
                    timeout=30.0
                )
                try:
                    duration = float(duration_str)
                    await scanner.scan_once(duration)
                except ValueError:
                    print("Invalid duration. Please enter a number.")
            elif choice == '5':
                print("\nExiting...")
                break
            else:
                print("Invalid choice. Please select 1-5.")
        
        except asyncio.TimeoutError:
            print("\nTimeout - exiting")
            break
        except KeyboardInterrupt:
            print("\nInterrupted - exiting")
            break
        except Exception as e:
            print(f"\nError: {e}")
            break
    
    print("\n=== Scanner Exit ===")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nScanning interrupted by user")
    except Exception as e:
        print(f"\nError: {e}")