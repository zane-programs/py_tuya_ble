"""Core Tuya BLE device implementation."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import secrets
import time
from collections.abc import Callable
from struct import pack, unpack
from typing import Optional, Dict, List, Union

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from bleak.exc import BleakDBusError, BleakError
from Crypto.Cipher import AES

from .const import (
    CHARACTERISTIC_NOTIFY,
    CHARACTERISTIC_WRITE,
    GATT_MTU,
    MANUFACTURER_DATA_ID,
    RESPONSE_WAIT_TIMEOUT,
    SERVICE_UUID,
    TuyaBLECode,
    TuyaBLEDataPointType,
)
from .exceptions import (
    TuyaBLEDataCRCError,
    TuyaBLEDataFormatError,
    TuyaBLEDataLengthError,
    TuyaBLEDeviceError,
    TuyaBLEEnumValueError,
)
from .manager import TuyaBLEDeviceCredentials, TuyaBLEDeviceManager

_LOGGER = logging.getLogger(__name__)


class TuyaBLEDataPoint:
    """Represents a single datapoint on a Tuya BLE device."""
    
    def __init__(
        self,
        owner: TuyaBLEDataPoints,
        id: int,
        timestamp: float,
        flags: int,
        type: TuyaBLEDataPointType,
        value: Union[bytes, bool, int, str],
    ) -> None:
        """Initialize a datapoint."""
        self._owner = owner
        self._id = id
        self._value = value
        self._changed_by_device = False
        self._update_from_device(timestamp, flags, type, value)

    def _update_from_device(
        self,
        timestamp: float,
        flags: int,
        type: TuyaBLEDataPointType,
        value: Union[bytes, bool, int, str],
    ) -> None:
        """Update datapoint value from device."""
        self._timestamp = timestamp
        self._flags = flags
        self._type = type
        self._changed_by_device = self._value != value
        self._value = value

    def _get_value(self) -> bytes:
        """Get the value as bytes for transmission."""
        match self._type:
            case TuyaBLEDataPointType.DT_RAW | TuyaBLEDataPointType.DT_BITMAP:
                return self._value
            case TuyaBLEDataPointType.DT_BOOL:
                return pack(">B", 1 if self._value else 0)
            case TuyaBLEDataPointType.DT_VALUE:
                return pack(">i", self._value)
            case TuyaBLEDataPointType.DT_ENUM:
                if self._value > 0xFFFF:
                    return pack(">I", self._value)
                elif self._value > 0xFF:
                    return pack(">H", self._value)
                else:
                    return pack(">B", self._value)
            case TuyaBLEDataPointType.DT_STRING:
                return self._value.encode()

    @property
    def id(self) -> int:
        """Get the datapoint ID."""
        return self._id

    @property
    def timestamp(self) -> float:
        """Get the last update timestamp."""
        return self._timestamp

    @property
    def flags(self) -> int:
        """Get the datapoint flags."""
        return self._flags

    @property
    def type(self) -> TuyaBLEDataPointType:
        """Get the datapoint type."""
        return self._type

    @property
    def value(self) -> Union[bytes, bool, int, str]:
        """Get the current value."""
        return self._value

    @property
    def changed_by_device(self) -> bool:
        """Check if the value was changed by the device."""
        return self._changed_by_device

    async def set_value(self, value: Union[bytes, bool, int, str]) -> None:
        """
        Set the datapoint value and send it to the device.
        
        Args:
            value: The new value to set
        
        Raises:
            TuyaBLEEnumValueError: If enum value is invalid
        """
        match self._type:
            case TuyaBLEDataPointType.DT_RAW | TuyaBLEDataPointType.DT_BITMAP:
                self._value = bytes(value)
            case TuyaBLEDataPointType.DT_BOOL:
                self._value = bool(value)
            case TuyaBLEDataPointType.DT_VALUE:
                self._value = int(value)
            case TuyaBLEDataPointType.DT_ENUM:
                value = int(value)
                if value >= 0:
                    self._value = value
                else:
                    raise TuyaBLEEnumValueError()
            case TuyaBLEDataPointType.DT_STRING:
                self._value = str(value)

        self._changed_by_device = False
        await self._owner._update_from_user(self._id)


class TuyaBLEDataPoints:
    """Collection of datapoints for a Tuya BLE device."""
    
    def __init__(self, owner: TuyaBLEDevice) -> None:
        """Initialize the datapoints collection."""
        self._owner = owner
        self._datapoints: Dict[int, TuyaBLEDataPoint] = {}
        self._update_started: int = 0
        self._updated_datapoints: List[int] = []

    def __len__(self) -> int:
        """Get the number of datapoints."""
        return len(self._datapoints)

    def __getitem__(self, key: int) -> Optional[TuyaBLEDataPoint]:
        """Get a datapoint by ID."""
        return self._datapoints.get(key)

    def has_id(self, id: int, type: Optional[TuyaBLEDataPointType] = None) -> bool:
        """
        Check if a datapoint exists.
        
        Args:
            id: Datapoint ID
            type: Optional type to verify
        
        Returns:
            True if the datapoint exists (and matches type if specified)
        """
        return (id in self._datapoints) and (
            (type is None) or (self._datapoints[id].type == type)
        )

    def get_or_create(
        self,
        id: int,
        type: TuyaBLEDataPointType,
        value: Optional[Union[bytes, bool, int, str]] = None,
    ) -> TuyaBLEDataPoint:
        """
        Get an existing datapoint or create a new one.
        
        Args:
            id: Datapoint ID
            type: Datapoint type
            value: Initial value
        
        Returns:
            The datapoint
        """
        datapoint = self._datapoints.get(id)
        if datapoint:
            return datapoint
        datapoint = TuyaBLEDataPoint(self, id, time.time(), 0, type, value)
        self._datapoints[id] = datapoint
        return datapoint

    def begin_update(self) -> None:
        """Begin a batch update of datapoints."""
        self._update_started += 1

    async def end_update(self) -> None:
        """End a batch update and send all changes to the device."""
        if self._update_started > 0:
            self._update_started -= 1
            if self._update_started == 0 and len(self._updated_datapoints) > 0:
                await self._owner._send_datapoints(self._updated_datapoints)
                self._updated_datapoints = []

    def _update_from_device(
        self,
        dp_id: int,
        timestamp: float,
        flags: int,
        type: TuyaBLEDataPointType,
        value: Union[bytes, bool, int, str],
    ) -> None:
        """Update a datapoint from device data."""
        dp = self._datapoints.get(dp_id)
        if dp:
            dp._update_from_device(timestamp, flags, type, value)
        else:
            self._datapoints[dp_id] = TuyaBLEDataPoint(
                self, dp_id, timestamp, flags, type, value
            )

    async def _update_from_user(self, dp_id: int) -> None:
        """Handle user update of a datapoint."""
        if self._update_started > 0:
            if dp_id in self._updated_datapoints:
                self._updated_datapoints.remove(dp_id)
            self._updated_datapoints.append(dp_id)
        else:
            await self._owner._send_datapoints([dp_id])


class TuyaBLEDevice:
    """
    Main class for interacting with a Tuya BLE device.
    
    This class handles all communication with a Tuya Smart device over BLE,
    including pairing, authentication, and datapoint management.
    """
    
    def __init__(
        self,
        device_manager: TuyaBLEDeviceManager,
        ble_device: BLEDevice,
        advertisement_data: Optional[AdvertisementData] = None,
    ) -> None:
        """
        Initialize a Tuya BLE device.
        
        Args:
            device_manager: Manager for device credentials
            ble_device: The BLE device to connect to
            advertisement_data: Optional advertisement data from scanning
        """
        self._device_manager = device_manager
        self._device_info: Optional[TuyaBLEDeviceCredentials] = None
        self._ble_device = ble_device
        self._advertisement_data = advertisement_data
        self._operation_lock = asyncio.Lock()
        self._connect_lock = asyncio.Lock()
        self._client: Optional[BleakClient] = None
        self._expected_disconnect = False
        self._connected_callbacks: List[Callable[[], None]] = []
        self._callbacks: List[Callable[[List[TuyaBLEDataPoint]], None]] = []
        self._disconnected_callbacks: List[Callable[[], None]] = []
        self._current_seq_num = 1
        self._seq_num_lock = asyncio.Lock()

        self._is_bound = False
        self._flags = 0
        self._protocol_version = 2

        self._device_version: str = ""
        self._protocol_version_str: str = ""
        self._hardware_version: str = ""

        self._auth_key: Optional[bytes] = None
        self._local_key: Optional[bytes] = None
        self._login_key: Optional[bytes] = None
        self._session_key: Optional[bytes] = None

        self._is_paired = False

        self._input_buffer: Optional[bytearray] = None
        self._input_expected_packet_num = 0
        self._input_expected_length = 0
        self._input_expected_responses: Dict[int, Optional[asyncio.Future]] = {}

        self._datapoints = TuyaBLEDataPoints(self)

    def set_ble_device_and_advertisement_data(
        self, ble_device: BLEDevice, advertisement_data: AdvertisementData
    ) -> None:
        """Update the BLE device and advertisement data."""
        self._ble_device = ble_device
        self._advertisement_data = advertisement_data

    async def initialize(self) -> None:
        """Initialize the device by loading credentials and parsing advertisement."""
        _LOGGER.debug("%s: Initializing", self.address)
        if await self._update_device_info():
            self._decode_advertisement_data()

    async def connect(self) -> None:
        """Connect to the device and perform pairing."""
        await self._ensure_connected()

    async def disconnect(self) -> None:
        """Disconnect from the device."""
        await self._execute_disconnect()

    async def update(self) -> None:
        """Request a status update from the device."""
        _LOGGER.debug("%s: Updating", self.address)
        await self._send_packet(TuyaBLECode.FUN_SENDER_DEVICE_STATUS, bytes())

    @property
    def address(self) -> str:
        """Get the device MAC address."""
        return self._ble_device.address

    @property
    def name(self) -> str:
        """Get the device name."""
        if self._device_info:
            return self._device_info.device_name or self._ble_device.name or self.address
        return self._ble_device.name or self.address

    @property
    def rssi(self) -> Optional[int]:
        """Get the device RSSI."""
        if self._advertisement_data:
            return self._advertisement_data.rssi
        return None

    @property
    def is_connected(self) -> bool:
        """Check if the device is connected."""
        return self._client is not None and self._client.is_connected

    @property
    def is_paired(self) -> bool:
        """Check if the device is paired."""
        return self._is_paired

    @property
    def datapoints(self) -> TuyaBLEDataPoints:
        """Get the device datapoints."""
        return self._datapoints

    @property
    def device_version(self) -> str:
        """Get the device firmware version."""
        return self._device_version

    @property
    def hardware_version(self) -> str:
        """Get the device hardware version."""
        return self._hardware_version

    @property
    def protocol_version(self) -> str:
        """Get the protocol version."""
        return self._protocol_version_str

    def register_callback(
        self, callback: Callable[[List[TuyaBLEDataPoint]], None]
    ) -> Callable[[], None]:
        """
        Register a callback for datapoint updates.
        
        Args:
            callback: Function to call when datapoints are updated
        
        Returns:
            Function to unregister the callback
        """
        def unregister_callback() -> None:
            self._callbacks.remove(callback)

        self._callbacks.append(callback)
        return unregister_callback

    def register_connected_callback(
        self, callback: Callable[[], None]
    ) -> Callable[[], None]:
        """
        Register a callback for connection events.
        
        Args:
            callback: Function to call when connected
        
        Returns:
            Function to unregister the callback
        """
        def unregister_callback() -> None:
            self._connected_callbacks.remove(callback)

        self._connected_callbacks.append(callback)
        return unregister_callback

    def register_disconnected_callback(
        self, callback: Callable[[], None]
    ) -> Callable[[], None]:
        """
        Register a callback for disconnection events.
        
        Args:
            callback: Function to call when disconnected
        
        Returns:
            Function to unregister the callback
        """
        def unregister_callback() -> None:
            self._disconnected_callbacks.remove(callback)

        self._disconnected_callbacks.append(callback)
        return unregister_callback

    # Internal methods (simplified versions of the original)
    
    async def _update_device_info(self) -> bool:
        """Load device credentials from the manager."""
        if self._device_info is None:
            if self._device_manager:
                self._device_info = await self._device_manager.get_device_credentials(
                    self._ble_device.address, False
                )
            if self._device_info:
                self._local_key = self._device_info.local_key[:6].encode()
                self._login_key = hashlib.md5(self._local_key).digest()

        return self._device_info is not None

    def _decode_advertisement_data(self) -> None:
        """Decode advertisement data to extract device information."""
        raw_product_id: Optional[bytes] = None
        raw_uuid: Optional[bytes] = None
        
        if self._advertisement_data:
            if self._advertisement_data.service_data:
                service_data = self._advertisement_data.service_data.get(SERVICE_UUID)
                if service_data and len(service_data) > 1:
                    if service_data[0] == 0:
                        raw_product_id = service_data[1:]

            if self._advertisement_data.manufacturer_data:
                manufacturer_data = self._advertisement_data.manufacturer_data.get(
                    MANUFACTURER_DATA_ID
                )
                if manufacturer_data and len(manufacturer_data) > 6:
                    self._is_bound = (manufacturer_data[0] & 0x80) != 0
                    self._protocol_version = manufacturer_data[1]
                    raw_uuid = manufacturer_data[6:]
                    if raw_product_id and raw_uuid:
                        key = hashlib.md5(raw_product_id).digest()
                        cipher = AES.new(key, AES.MODE_CBC, key)
                        raw_uuid = cipher.decrypt(raw_uuid)
                        self._uuid = raw_uuid.decode("utf-8")

    def _build_pairing_request(self) -> bytes:
        """Build a pairing request packet."""
        result = bytearray()
        
        if self._device_info:
            result += self._device_info.uuid.encode()
            result += self._local_key
            result += self._device_info.device_id.encode()
        
        # Pad to 44 bytes
        while len(result) < 44:
            result += b"\x00"
        
        return bytes(result)

    async def _ensure_connected(self) -> None:
        """Ensure the device is connected and paired."""
        if self._expected_disconnect:
            return
        
        if self._client and self._client.is_connected and self._is_paired:
            return
        
        async with self._connect_lock:
            # Check again while holding the lock
            if self._client and self._client.is_connected and self._is_paired:
                return
            
            try:
                _LOGGER.debug("%s: Connecting; RSSI: %s", self.address, self.rssi)
                
                # Create client and connect
                self._client = BleakClient(self._ble_device.address)
                await self._client.connect()
                
                if self._client.is_connected:
                    _LOGGER.debug("%s: Connected; RSSI: %s", self.address, self.rssi)
                    
                    # Start notifications
                    await self._client.start_notify(
                        CHARACTERISTIC_NOTIFY, self._notification_handler
                    )
                    
                    # Request device info
                    _LOGGER.debug("%s: Sending device info request", self.address)
                    await self._send_packet_while_connected(
                        TuyaBLECode.FUN_SENDER_DEVICE_INFO,
                        bytes(0),
                        0,
                        True,
                    )
                    
                    # Send pairing request
                    _LOGGER.debug("%s: Sending pairing request", self.address)
                    await self._send_packet_while_connected(
                        TuyaBLECode.FUN_SENDER_PAIR,
                        self._build_pairing_request(),
                        0,
                        True,
                    )
                    
                    if self._is_paired:
                        _LOGGER.debug("%s: Successfully connected and paired", self.address)
                        self._fire_connected_callbacks()
                    else:
                        _LOGGER.error("%s: Connected but not paired", self.address)
                        
            except Exception as e:
                _LOGGER.error("%s: Connection failed: %s", self.address, e, exc_info=True)
                self._client = None
                raise

    async def _execute_disconnect(self) -> None:
        """Execute disconnection from the device."""
        async with self._connect_lock:
            client = self._client
            self._expected_disconnect = True
            self._client = None
            if client and client.is_connected:
                await client.stop_notify(CHARACTERISTIC_NOTIFY)
                await client.disconnect()
        async with self._seq_num_lock:
            self._current_seq_num = 1

    def _fire_callbacks(self, datapoints: List[TuyaBLEDataPoint]) -> None:
        """Fire datapoint update callbacks."""
        for callback in self._callbacks:
            callback(datapoints)

    def _fire_connected_callbacks(self) -> None:
        """Fire connection callbacks."""
        for callback in self._connected_callbacks:
            callback()

    def _fire_disconnected_callbacks(self) -> None:
        """Fire disconnection callbacks."""
        for callback in self._disconnected_callbacks:
            callback()

    # CRC and packet building methods
    
    @staticmethod
    def _calc_crc16(data: bytes) -> int:
        """Calculate CRC16 checksum."""
        crc = 0xFFFF
        for byte in data:
            crc ^= byte & 255
            for _ in range(8):
                tmp = crc & 1
                crc >>= 1
                if tmp != 0:
                    crc ^= 0xA001
        return crc

    @staticmethod
    def _pack_int(value: int) -> bytearray:
        """Pack an integer using variable-length encoding."""
        result = bytearray()
        while True:
            curr_byte = value & 0x7F
            value >>= 7
            if value != 0:
                curr_byte |= 0x80
            result += pack(">B", curr_byte)
            if value == 0:
                break
        return result

    @staticmethod
    def _unpack_int(data: bytes, start_pos: int) -> tuple[int, int]:
        """Unpack a variable-length encoded integer."""
        result = 0
        offset = 0
        while offset < 5:
            pos = start_pos + offset
            if pos >= len(data):
                raise TuyaBLEDataFormatError()
            curr_byte = data[pos]
            result |= (curr_byte & 0x7F) << (offset * 7)
            offset += 1
            if (curr_byte & 0x80) == 0:
                break
        if offset > 4:
            raise TuyaBLEDataFormatError()
        return result, start_pos + offset

    def _build_packets(
        self,
        seq_num: int,
        code: TuyaBLECode,
        data: bytes,
        response_to: int = 0,
    ) -> List[bytes]:
        """Build encrypted packets for transmission."""
        # Select encryption key based on command
        iv = secrets.token_bytes(16)
        if code == TuyaBLECode.FUN_SENDER_DEVICE_INFO:
            key = self._login_key
            security_flag = b"\x04"
        else:
            key = self._session_key
            security_flag = b"\x05"

        # Build raw packet
        raw = bytearray()
        raw += pack(">IIHH", seq_num, response_to, code.value, len(data))
        raw += data
        crc = self._calc_crc16(raw)
        raw += pack(">H", crc)
        
        # Pad to 16-byte boundary
        while len(raw) % 16 != 0:
            raw += b"\x00"

        # Encrypt packet
        cipher = AES.new(key, AES.MODE_CBC, iv)
        encrypted = security_flag + iv + cipher.encrypt(raw)

        # Split into MTU-sized packets
        command = []
        packet_num = 0
        pos = 0
        length = len(encrypted)
        
        while pos < length:
            packet = bytearray()
            packet += self._pack_int(packet_num)

            if packet_num == 0:
                packet += self._pack_int(length)
                packet += pack(">B", self._protocol_version << 4)

            data_part = encrypted[pos:pos + GATT_MTU - len(packet)]
            packet += data_part
            command.append(bytes(packet))

            pos += len(data_part)
            packet_num += 1

        return command

    async def _get_seq_num(self) -> int:
        """Get the next sequence number."""
        async with self._seq_num_lock:
            result = self._current_seq_num
            self._current_seq_num += 1
        return result

    async def _send_packet(
        self,
        code: TuyaBLECode,
        data: bytes,
        wait_for_response: bool = True,
    ) -> None:
        """Send a packet to the device."""
        if self._expected_disconnect:
            return
        await self._ensure_connected()
        if self._expected_disconnect:
            return
        await self._send_packet_while_connected(code, data, 0, wait_for_response)

    async def _send_response(
        self,
        code: TuyaBLECode,
        data: bytes,
        response_to: int,
    ) -> None:
        """Send a response packet to the device."""
        if self._client and self._client.is_connected:
            await self._send_packet_while_connected(code, data, response_to, False)

    async def _send_packet_while_connected(
        self,
        code: TuyaBLECode,
        data: bytes,
        response_to: int,
        wait_for_response: bool,
    ) -> bool:
        """Send a packet while connected."""
        result = True
        future: Optional[asyncio.Future] = None
        seq_num = await self._get_seq_num()
        
        if wait_for_response:
            future = asyncio.Future()
            self._input_expected_responses[seq_num] = future

        if response_to > 0:
            _LOGGER.debug(
                "%s: Sending packet: #%s %s in response to #%s",
                self.address,
                seq_num,
                code.name,
                response_to,
            )
        else:
            _LOGGER.debug(
                "%s: Sending packet: #%s %s",
                self.address,
                seq_num,
                code.name,
            )
        
        packets = self._build_packets(seq_num, code, data, response_to)
        await self._int_send_packet_while_connected(packets)
        
        if future:
            try:
                await asyncio.wait_for(future, RESPONSE_WAIT_TIMEOUT)
            except asyncio.TimeoutError:
                _LOGGER.error(
                    "%s: timeout receiving response, RSSI: %s",
                    self.address,
                    self.rssi,
                )
                result = False
            self._input_expected_responses.pop(seq_num, None)

        return result

    async def _int_send_packet_while_connected(
        self,
        packets: List[bytes],
    ) -> None:
        """Internal method to send packets."""
        async with self._operation_lock:
            try:
                await self._send_packets_locked(packets)
            except Exception as e:
                _LOGGER.error(
                    "%s: communication failed: %s",
                    self.address,
                    e,
                    exc_info=True,
                )
                raise

    async def _send_packets_locked(self, packets: List[bytes]) -> None:
        """Send packets with lock held."""
        for packet in packets:
            if self._client:
                try:
                    await self._client.write_gatt_char(
                        CHARACTERISTIC_WRITE,
                        packet,
                        False,
                    )
                except Exception as e:
                    _LOGGER.error(
                        "%s: Error during sending packet: %s",
                        self.address,
                        e,
                        exc_info=True,
                    )
                    raise BleakError() from e
            else:
                _LOGGER.error(
                    "%s: Client disconnected during sending packet",
                    self.address,
                )
                raise BleakError()

    def _get_key(self, security_flag: int) -> Optional[bytes]:
        """Get encryption key based on security flag."""
        if security_flag == 1:
            return self._auth_key
        elif security_flag == 4:
            return self._login_key
        elif security_flag == 5:
            return self._session_key
        return None

    def _parse_timestamp(self, data: bytes, start_pos: int) -> tuple[float, int]:
        """Parse timestamp from data."""
        pos = start_pos
        if pos >= len(data):
            raise TuyaBLEDataLengthError()
        
        time_type = data[pos]
        pos += 1
        end_pos = pos
        
        match time_type:
            case 0:
                end_pos += 13
                if end_pos > len(data):
                    raise TuyaBLEDataLengthError()
                timestamp = int(data[pos:end_pos].decode()) / 1000
            case 1:
                end_pos += 4
                if end_pos > len(data):
                    raise TuyaBLEDataLengthError()
                timestamp = int.from_bytes(data[pos:end_pos], "big") * 1.0
            case _:
                raise TuyaBLEDataFormatError()

        _LOGGER.debug(
            "%s: Received timestamp: %s",
            self.address,
            time.ctime(timestamp),
        )
        return timestamp, end_pos

    def _parse_datapoints_v3(
        self, timestamp: float, flags: int, data: bytes, start_pos: int
    ) -> None:
        """Parse datapoints from received data."""
        datapoints: List[TuyaBLEDataPoint] = []

        pos = start_pos
        while len(data) - pos >= 4:
            id = data[pos]
            pos += 1
            _type = data[pos]
            if _type > TuyaBLEDataPointType.DT_BITMAP.value:
                raise TuyaBLEDataFormatError()
            type = TuyaBLEDataPointType(_type)
            pos += 1
            data_len = data[pos]
            pos += 1
            next_pos = pos + data_len
            if next_pos > len(data):
                raise TuyaBLEDataLengthError()
            raw_value = data[pos:next_pos]
            
            match type:
                case TuyaBLEDataPointType.DT_RAW | TuyaBLEDataPointType.DT_BITMAP:
                    value = raw_value
                case TuyaBLEDataPointType.DT_BOOL:
                    value = int.from_bytes(raw_value, "big") != 0
                case TuyaBLEDataPointType.DT_VALUE | TuyaBLEDataPointType.DT_ENUM:
                    value = int.from_bytes(raw_value, "big", signed=True)
                case TuyaBLEDataPointType.DT_STRING:
                    value = raw_value.decode()

            _LOGGER.debug(
                "%s: Received datapoint update, id: %s, type: %s, value: %s",
                self.address,
                id,
                type.name,
                value,
            )
            self._datapoints._update_from_device(id, timestamp, flags, type, value)
            datapoints.append(self._datapoints[id])
            pos = next_pos

        self._fire_callbacks(datapoints)

    def _handle_command_or_response(
        self, seq_num: int, response_to: int, code: TuyaBLECode, data: bytes
    ) -> None:
        """Handle received command or response."""
        result = 0

        match code:
            case TuyaBLECode.FUN_SENDER_DEVICE_INFO:
                if len(data) < 46:
                    raise TuyaBLEDataLengthError()

                self._device_version = f"{data[0]}.{data[1]}"
                self._protocol_version_str = f"{data[2]}.{data[3]}"
                self._hardware_version = f"{data[12]}.{data[13]}"

                self._protocol_version = data[2]
                self._flags = data[4]
                self._is_bound = data[5] != 0

                srand = data[6:12]
                self._session_key = hashlib.md5(self._local_key + srand).digest()
                self._auth_key = data[14:46]

            case TuyaBLECode.FUN_SENDER_PAIR:
                if len(data) != 1:
                    raise TuyaBLEDataLengthError()
                result = data[0]
                if result == 2:
                    _LOGGER.debug("%s: Device is already paired", self.address)
                    result = 0
                self._is_paired = result == 0

            case TuyaBLECode.FUN_SENDER_DEVICE_STATUS:
                if len(data) != 1:
                    raise TuyaBLEDataLengthError()
                result = data[0]

            case TuyaBLECode.FUN_RECEIVE_TIME1_REQ:
                if len(data) != 0:
                    raise TuyaBLEDataLengthError()

                timestamp = int(time.time_ns() / 1000000)
                timezone = -int(time.timezone / 36)
                data = str(timestamp).encode() + pack(">h", timezone)
                asyncio.create_task(self._send_response(code, data, seq_num))

            case TuyaBLECode.FUN_RECEIVE_TIME2_REQ:
                if len(data) != 0:
                    raise TuyaBLEDataLengthError()

                time_str = time.localtime()
                timezone = -int(time.timezone / 36)
                data = pack(
                    ">BBBBBBBh",
                    time_str.tm_year % 100,
                    time_str.tm_mon,
                    time_str.tm_mday,
                    time_str.tm_hour,
                    time_str.tm_min,
                    time_str.tm_sec,
                    time_str.tm_wday,
                    timezone,
                )
                asyncio.create_task(self._send_response(code, data, seq_num))

            case TuyaBLECode.FUN_RECEIVE_DP:
                self._parse_datapoints_v3(time.time(), 0, data, 0)
                asyncio.create_task(self._send_response(code, bytes(0), seq_num))

            case TuyaBLECode.FUN_RECEIVE_SIGN_DP:
                dp_seq_num = int.from_bytes(data[:2], "big")
                flags = data[2]
                self._parse_datapoints_v3(time.time(), flags, data, 2)
                data = pack(">HBB", dp_seq_num, flags, 0)
                asyncio.create_task(self._send_response(code, data, seq_num))

            case TuyaBLECode.FUN_RECEIVE_TIME_DP:
                timestamp, pos = self._parse_timestamp(data, 0)
                self._parse_datapoints_v3(timestamp, 0, data, pos)
                asyncio.create_task(self._send_response(code, bytes(0), seq_num))

            case TuyaBLECode.FUN_RECEIVE_SIGN_TIME_DP:
                dp_seq_num = int.from_bytes(data[:2], "big")
                flags = data[2]
                timestamp, pos = self._parse_timestamp(data, 3)
                self._parse_datapoints_v3(time.time(), flags, data, pos)
                data = pack(">HBB", dp_seq_num, flags, 0)
                asyncio.create_task(self._send_response(code, data, seq_num))

        if response_to != 0:
            future = self._input_expected_responses.pop(response_to, None)
            if future:
                _LOGGER.debug(
                    "%s: Received expected response to #%s, result: %s",
                    self.address,
                    response_to,
                    result,
                )
                if result == 0:
                    future.set_result(result)
                else:
                    future.set_exception(TuyaBLEDeviceError(result))

    def _clean_input(self) -> None:
        """Clean input buffer."""
        self._input_buffer = None
        self._input_expected_packet_num = 0
        self._input_expected_length = 0

    def _parse_input(self) -> None:
        """Parse received input buffer."""
        security_flag = self._input_buffer[0]
        key = self._get_key(security_flag)
        iv = self._input_buffer[1:17]
        encrypted = self._input_buffer[17:]

        self._clean_input()

        cipher = AES.new(key, AES.MODE_CBC, iv)
        raw = cipher.decrypt(encrypted)

        seq_num, response_to, _code, length = unpack(">IIHH", raw[:12])

        data_end_pos = length + 12
        raw_length = len(raw)
        if raw_length < data_end_pos:
            raise TuyaBLEDataLengthError()
        if raw_length > data_end_pos:
            calc_crc = self._calc_crc16(raw[:data_end_pos])
            data_crc, = unpack(">H", raw[data_end_pos:data_end_pos + 2])
            if calc_crc != data_crc:
                raise TuyaBLEDataCRCError()
        data = raw[12:data_end_pos]

        try:
            code = TuyaBLECode(_code)
        except ValueError:
            _LOGGER.debug(
                "%s: Received unknown message: #%s %x, response to #%s, data %s",
                self.address,
                seq_num,
                _code,
                response_to,
                data.hex(),
            )
            return

        if response_to != 0:
            _LOGGER.debug(
                "%s: Received: #%s %s, response to #%s",
                self.address,
                seq_num,
                code.name,
                response_to,
            )
        else:
            _LOGGER.debug(
                "%s: Received: #%s %s",
                self.address,
                seq_num,
                code.name,
            )

        self._handle_command_or_response(seq_num, response_to, code, data)

    def _notification_handler(self, sender: int, data: bytearray) -> None:
        """Handle BLE notifications."""
        _LOGGER.debug("%s: Packet received: %s", self.address, data.hex())

        pos = 0
        packet_num, pos = self._unpack_int(data, pos)

        if packet_num < self._input_expected_packet_num:
            _LOGGER.error(
                "%s: Unexpected packet (number %s) in notifications, expected %s",
                self.address,
                packet_num,
                self._input_expected_packet_num,
            )
            self._clean_input()

        if packet_num == self._input_expected_packet_num:
            if packet_num == 0:
                self._input_buffer = bytearray()
                self._input_expected_length, pos = self._unpack_int(data, pos)
                pos += 1
            self._input_buffer += data[pos:]
            self._input_expected_packet_num += 1
        else:
            _LOGGER.error(
                "%s: Missing packet (number %s) in notifications, received %s",
                self.address,
                self._input_expected_packet_num,
                packet_num,
            )
            self._clean_input()
            return

        if len(self._input_buffer) > self._input_expected_length:
            _LOGGER.error(
                "%s: Unexpected length of data in notifications, "
                "received %s expected %s",
                self.address,
                len(self._input_buffer),
                self._input_expected_length,
            )
            self._clean_input()
            return
        elif len(self._input_buffer) == self._input_expected_length:
            self._parse_input()

    async def _send_datapoints_v3(self, datapoint_ids: List[int]) -> None:
        """Send datapoint updates to the device."""
        data = bytearray()
        for dp_id in datapoint_ids:
            dp = self._datapoints[dp_id]
            if dp:
                value = dp._get_value()
                _LOGGER.debug(
                    "%s: Sending datapoint update, id: %s, type: %s, value: %s",
                    self.address,
                    dp.id,
                    dp.type.name,
                    dp.value,
                )
                data += pack(">BBB", dp.id, int(dp.type.value), len(value))
                data += value

        await self._send_packet(TuyaBLECode.FUN_SENDER_DPS, bytes(data))

    async def _send_datapoints(self, datapoint_ids: List[int]) -> None:
        """Send datapoint updates to the device."""
        if self._protocol_version == 3:
            await self._send_datapoints_v3(datapoint_ids)
        else:
            raise TuyaBLEDeviceError(0)