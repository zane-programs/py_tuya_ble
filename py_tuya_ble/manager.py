"""Device credentials management for Tuya BLE devices."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Optional


@dataclass
class TuyaBLEDeviceCredentials:
    """Credentials and metadata for a Tuya BLE device."""
    
    uuid: str                    # Device UUID
    local_key: str               # Local encryption key
    device_id: str               # Device ID
    category: str                # Device category
    product_id: str              # Product ID
    device_name: Optional[str] = None   # Human-readable device name
    product_model: Optional[str] = None # Product model
    product_name: Optional[str] = None  # Product name

    def __str__(self):
        """Return a string representation with sensitive data masked."""
        return (
            "uuid: xxxxxxxxxxxxxxxx, "
            "local_key: xxxxxxxxxxxxxxxx, "
            "device_id: xxxxxxxxxxxxxxxx, "
            f"category: {self.category}, "
            f"product_id: {self.product_id}, "
            f"device_name: {self.device_name}, "
            f"product_model: {self.product_model}, "
            f"product_name: {self.product_name}"
        )


class TuyaBLEDeviceManager:
    """
    Manager for storing and retrieving Tuya BLE device credentials.
    
    This implementation stores credentials in a local JSON file.
    You can extend this class to implement different storage backends
    (e.g., database, cloud storage, encrypted storage).
    """
    
    def __init__(self, storage_path: Optional[Path] = None):
        """
        Initialize the device manager.
        
        Args:
            storage_path: Path to the JSON file for storing credentials.
                         Defaults to ~/.py_tuya_ble/devices.json
        """
        if storage_path is None:
            storage_path = Path.home() / ".py_tuya_ble" / "devices.json"
        
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Cache for loaded devices
        self._devices: Dict[str, TuyaBLEDeviceCredentials] = {}
        self._load_devices()
    
    def _load_devices(self) -> None:
        """Load devices from storage file."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                    for address, device_data in data.items():
                        self._devices[address] = TuyaBLEDeviceCredentials(**device_data)
            except (json.JSONDecodeError, TypeError) as e:
                print(f"Error loading devices from {self.storage_path}: {e}")
    
    def _save_devices(self) -> None:
        """Save devices to storage file."""
        data = {
            address: asdict(device)
            for address, device in self._devices.items()
        }
        with open(self.storage_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    async def get_device_credentials(
        self,
        address: str,
        force_update: bool = False,
        save_data: bool = False,
    ) -> Optional[TuyaBLEDeviceCredentials]:
        """
        Get credentials for a Tuya BLE device by its MAC address.
        
        Args:
            address: MAC address of the device
            force_update: Force reload from storage (not used in this implementation)
            save_data: Save any changes back to storage
        
        Returns:
            Device credentials if found, None otherwise
        """
        if force_update:
            self._load_devices()
        
        device = self._devices.get(address)
        
        if save_data:
            self._save_devices()
        
        return device
    
    def add_device(
        self,
        address: str,
        uuid: str,
        local_key: str,
        device_id: str,
        category: str,
        product_id: str,
        device_name: Optional[str] = None,
        product_model: Optional[str] = None,
        product_name: Optional[str] = None,
    ) -> TuyaBLEDeviceCredentials:
        """
        Add or update a device in the manager.
        
        Args:
            address: MAC address of the device
            uuid: Device UUID
            local_key: Local encryption key
            device_id: Device ID
            category: Device category
            product_id: Product ID
            device_name: Human-readable device name
            product_model: Product model
            product_name: Product name
        
        Returns:
            The created or updated device credentials
        """
        device = TuyaBLEDeviceCredentials(
            uuid=uuid,
            local_key=local_key,
            device_id=device_id,
            category=category,
            product_id=product_id,
            device_name=device_name,
            product_model=product_model,
            product_name=product_name,
        )
        
        self._devices[address] = device
        self._save_devices()
        
        return device
    
    def remove_device(self, address: str) -> bool:
        """
        Remove a device from the manager.
        
        Args:
            address: MAC address of the device to remove
        
        Returns:
            True if device was removed, False if not found
        """
        if address in self._devices:
            del self._devices[address]
            self._save_devices()
            return True
        return False
    
    def list_devices(self) -> Dict[str, TuyaBLEDeviceCredentials]:
        """
        List all stored devices.
        
        Returns:
            Dictionary mapping MAC addresses to device credentials
        """
        return self._devices.copy()
    
    @classmethod
    def check_and_create_device_credentials(
        cls,
        uuid: Optional[str],
        local_key: Optional[str],
        device_id: Optional[str],
        category: Optional[str],
        product_id: Optional[str],
        device_name: Optional[str] = None,
        product_model: Optional[str] = None,
        product_name: Optional[str] = None,
    ) -> Optional[TuyaBLEDeviceCredentials]:
        """
        Validate and create device credentials if all required fields are present.
        
        Args:
            uuid: Device UUID
            local_key: Local encryption key
            device_id: Device ID
            category: Device category
            product_id: Product ID
            device_name: Human-readable device name
            product_model: Product model
            product_name: Product name
        
        Returns:
            Device credentials if all required fields are present, None otherwise
        """
        if all([uuid, local_key, device_id, category, product_id]):
            return TuyaBLEDeviceCredentials(
                uuid=uuid,
                local_key=local_key,
                device_id=device_id,
                category=category,
                product_id=product_id,
                device_name=device_name,
                product_model=product_model,
                product_name=product_name,
            )
        return None