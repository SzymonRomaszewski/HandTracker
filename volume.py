"""Adjust the default output device through the macOS audio service."""

from ctypes import CDLL, POINTER, Structure, byref, c_float, c_int32, c_uint32, c_void_p, sizeof


class Address(Structure):
    _fields_ = [("selector", c_uint32), ("scope", c_uint32), ("element", c_uint32)]


def address(selector: bytes, scope: bytes) -> Address:
    return Address(int.from_bytes(selector, "big"), int.from_bytes(scope, "big"), 0)


class OutputVolume:
    def __init__(self) -> None:
        core = CDLL("/System/Library/Frameworks/CoreAudio.framework/CoreAudio")
        service = CDLL("/System/Library/Frameworks/AudioToolbox.framework/AudioToolbox")
        self._get_device = core.AudioObjectGetPropertyData
        self._get_volume = service.AudioHardwareServiceGetPropertyData
        self._set_volume = service.AudioHardwareServiceSetPropertyData
        prefix = [c_uint32, POINTER(Address), c_uint32, c_void_p]
        for getter in (self._get_device, self._get_volume):
            getter.argtypes = [*prefix, POINTER(c_uint32), c_void_p]
            getter.restype = c_int32
        self._set_volume.argtypes = [*prefix, c_uint32, c_void_p]
        self._set_volume.restype = c_int32

    def adjust(self, delta: int) -> bool:
        device = c_uint32()
        size = c_uint32(sizeof(device))
        output = address(b"dOut", b"glob")
        if self._get_device(1, byref(output), 0, None, byref(size), byref(device)):
            return False
        level = c_float()
        size = c_uint32(sizeof(level))
        volume = address(b"vmvc", b"outp")
        if self._get_volume(device, byref(volume), 0, None, byref(size), byref(level)):
            return False
        level.value = max(0.0, min(1.0, level.value + delta / 100))
        return self._set_volume(device, byref(volume), 0, None, size, byref(level)) == 0
