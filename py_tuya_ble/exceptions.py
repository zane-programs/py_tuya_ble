"""Exception classes for Tuya BLE communication errors."""

from __future__ import annotations


class TuyaBLEError(Exception):
    """Base class for all Tuya BLE errors."""


class TuyaBLEEnumValueError(TuyaBLEError):
    """Raised when value assigned to DP_ENUM datapoint has unexpected type."""

    def __init__(self) -> None:
        super().__init__("Value of DP_ENUM datapoint must be unsigned integer")


class TuyaBLEDataFormatError(TuyaBLEError):
    """Raised when data in Tuya BLE structures is formatted incorrectly."""

    def __init__(self) -> None:
        super().__init__("Incoming packet is formatted incorrectly")


class TuyaBLEDataCRCError(TuyaBLEError):
    """Raised when data packet has invalid CRC checksum."""

    def __init__(self) -> None:
        super().__init__("Incoming packet has invalid CRC")


class TuyaBLEDataLengthError(TuyaBLEError):
    """Raised when data packet has invalid length."""

    def __init__(self) -> None:
        super().__init__("Incoming packet has invalid length")


class TuyaBLEDeviceError(TuyaBLEError):
    """Raised when Tuya BLE device returns an error in response to a command."""

    def __init__(self, code: int) -> None:
        super().__init__(f"BLE device returned error code {code}")