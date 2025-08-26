"""
py_tuya_ble - A standalone Python library for Tuya BLE devices.

This library provides a pure Python implementation for communicating with
Tuya Smart devices over Bluetooth Low Energy (BLE), completely independent
of Home Assistant or any other home automation framework.

Main Features:
- Direct BLE communication with Tuya devices
- Device pairing and authentication
- Reading and writing datapoints
- Support for various Tuya BLE device types
- Asynchronous operation using asyncio
- Comprehensive error handling
"""

from .const import TuyaBLECode, TuyaBLEDataPointType
from .exceptions import (
    TuyaBLEError,
    TuyaBLEDataCRCError,
    TuyaBLEDataFormatError,
    TuyaBLEDataLengthError,
    TuyaBLEDeviceError,
    TuyaBLEEnumValueError,
)
from .manager import TuyaBLEDeviceCredentials, TuyaBLEDeviceManager
from .device import TuyaBLEDataPoint, TuyaBLEDataPoints, TuyaBLEDevice

__version__ = "0.1.0"

__all__ = [
    # Core device classes
    "TuyaBLEDevice",
    "TuyaBLEDataPoint",
    "TuyaBLEDataPoints",
    # Management classes
    "TuyaBLEDeviceCredentials",
    "TuyaBLEDeviceManager",
    # Constants
    "TuyaBLECode",
    "TuyaBLEDataPointType",
    # Exceptions
    "TuyaBLEError",
    "TuyaBLEDataCRCError",
    "TuyaBLEDataFormatError",
    "TuyaBLEDataLengthError",
    "TuyaBLEDeviceError",
    "TuyaBLEEnumValueError",
]