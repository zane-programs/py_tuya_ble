"""Constants for Tuya BLE communication."""

from __future__ import annotations

from enum import Enum

# BLE Communication Constants
GATT_MTU = 20
DEFAULT_ATTEMPTS = 0xFFFF
RESPONSE_WAIT_TIMEOUT = 60

# BLE Characteristic UUIDs
CHARACTERISTIC_NOTIFY = "00002b10-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC_WRITE = "00002b11-0000-1000-8000-00805f9b34fb"

# Service UUID for Tuya BLE devices
SERVICE_UUID = "0000a201-0000-1000-8000-00805f9b34fb"

# Manufacturer data identifier
MANUFACTURER_DATA_ID = 0x07D0


class TuyaBLECode(Enum):
    """Function codes for Tuya BLE protocol communication."""
    
    # Sender functions (commands sent to device)
    FUN_SENDER_DEVICE_INFO = 0x0000
    FUN_SENDER_PAIR = 0x0001
    FUN_SENDER_DPS = 0x0002  # Send datapoint updates
    FUN_SENDER_DEVICE_STATUS = 0x0003
    FUN_SENDER_UNBIND = 0x0005
    FUN_SENDER_DEVICE_RESET = 0x0006
    
    # OTA (Over-The-Air) update functions
    FUN_SENDER_OTA_START = 0x000C
    FUN_SENDER_OTA_FILE = 0x000D
    FUN_SENDER_OTA_OFFSET = 0x000E
    FUN_SENDER_OTA_UPGRADE = 0x000F
    FUN_SENDER_OTA_OVER = 0x0010
    
    # Protocol v4 functions
    FUN_SENDER_DPS_V4 = 0x0027
    
    # Receiver functions (commands received from device)
    FUN_RECEIVE_DP = 0x8001  # Receive datapoint updates
    FUN_RECEIVE_TIME_DP = 0x8003
    FUN_RECEIVE_SIGN_DP = 0x8004
    FUN_RECEIVE_SIGN_TIME_DP = 0x8005
    
    # Protocol v4 receiver functions
    FUN_RECEIVE_DP_V4 = 0x8006
    FUN_RECEIVE_TIME_DP_V4 = 0x8007
    
    # Time synchronization requests
    FUN_RECEIVE_TIME1_REQ = 0x8011
    FUN_RECEIVE_TIME2_REQ = 0x8012


class TuyaBLEDataPointType(Enum):
    """Data types for Tuya BLE datapoints."""
    
    DT_RAW = 0      # Raw bytes data
    DT_BOOL = 1     # Boolean value (True/False)
    DT_VALUE = 2    # Integer value
    DT_STRING = 3   # String value
    DT_ENUM = 4     # Enumeration (integer representing a choice)
    DT_BITMAP = 5   # Bitmap/flags data