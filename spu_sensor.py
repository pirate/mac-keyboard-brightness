"""
reads the undocumented accelerometer on apple silicon macbooks
via iokit hid (AppleSPUHIDDevice, vendor page 0xFF00 usage 3)
only tested on macbook pro m3 pro
"""

import ctypes
import ctypes.util
import struct
import multiprocessing.shared_memory

# shm layout:
#   [0..3]   write_idx  u32, wraps at RING_CAP
#   [4..11]  total      u64, monotonic
#   [12..15] restarts   u32
#   [16..]   ring of RING_CAP * 12 bytes (3x i32: x, y, z)
RING_CAP = 8000
RING_ENTRY = 12
SHM_HEADER = 16
SHM_SIZE = SHM_HEADER + RING_CAP * RING_ENTRY
SHM_NAME = 'vib_detect_shm'

ACCEL_SCALE = 65536.0


def shm_write_sample(buf, x_raw, y_raw, z_raw):
    idx, = struct.unpack_from('<I', buf, 0)
    off = SHM_HEADER + idx * RING_ENTRY
    struct.pack_into('<iii', buf, off, x_raw, y_raw, z_raw)
    struct.pack_into('<I', buf, 0, (idx + 1) % RING_CAP)
    total, = struct.unpack_from('<Q', buf, 4)
    struct.pack_into('<Q', buf, 4, total + 1)


def shm_read_new(buf, last_total):
    total, = struct.unpack_from('<Q', buf, 4)
    n_new = total - last_total
    if n_new <= 0:
        return [], total
    if n_new > RING_CAP:
        n_new = RING_CAP
    idx, = struct.unpack_from('<I', buf, 0)
    samples = []
    start = (idx - n_new) % RING_CAP
    for i in range(n_new):
        pos = (start + i) % RING_CAP
        off = SHM_HEADER + pos * RING_ENTRY
        x, y, z = struct.unpack_from('<iii', buf, off)
        samples.append((x / ACCEL_SCALE, y / ACCEL_SCALE, z / ACCEL_SCALE))
    return samples, total


def sensor_worker(shm_name, restart_count):
    _iokit = ctypes.cdll.LoadLibrary(ctypes.util.find_library('IOKit'))
    _cf = ctypes.cdll.LoadLibrary(ctypes.util.find_library('CoreFoundation'))

    kCFAllocatorDefault = ctypes.c_void_p.in_dll(_cf, 'kCFAllocatorDefault')
    kCFRunLoopDefaultMode = ctypes.c_void_p.in_dll(_cf, 'kCFRunLoopDefaultMode')

    _iokit.IOServiceMatching.restype = ctypes.c_void_p
    _iokit.IOServiceMatching.argtypes = [ctypes.c_char_p]
    _iokit.IOServiceGetMatchingServices.restype = ctypes.c_int
    _iokit.IOServiceGetMatchingServices.argtypes = [
        ctypes.c_uint, ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint)]
    _iokit.IOIteratorNext.restype = ctypes.c_uint
    _iokit.IOIteratorNext.argtypes = [ctypes.c_uint]
    _iokit.IOObjectRelease.argtypes = [ctypes.c_uint]
    _iokit.IORegistryEntryCreateCFProperty.restype = ctypes.c_void_p
    _iokit.IORegistryEntryCreateCFProperty.argtypes = [
        ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint]
    _iokit.IORegistryEntrySetCFProperty.restype = ctypes.c_int
    _iokit.IORegistryEntrySetCFProperty.argtypes = [
        ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]
    _iokit.IOHIDDeviceCreate.restype = ctypes.c_void_p
    _iokit.IOHIDDeviceCreate.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    _iokit.IOHIDDeviceOpen.restype = ctypes.c_int
    _iokit.IOHIDDeviceOpen.argtypes = [ctypes.c_void_p, ctypes.c_int]
    _iokit.IOHIDDeviceRegisterInputReportCallback.restype = None
    _iokit.IOHIDDeviceRegisterInputReportCallback.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long,
        ctypes.c_void_p, ctypes.c_void_p]
    _iokit.IOHIDDeviceScheduleWithRunLoop.restype = None
    _iokit.IOHIDDeviceScheduleWithRunLoop.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]

    _cf.CFStringCreateWithCString.restype = ctypes.c_void_p
    _cf.CFStringCreateWithCString.argtypes = [
        ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]
    _cf.CFNumberCreate.restype = ctypes.c_void_p
    _cf.CFNumberCreate.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
    _cf.CFNumberGetValue.restype = ctypes.c_bool
    _cf.CFNumberGetValue.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
    _cf.CFRunLoopGetCurrent.restype = ctypes.c_void_p
    _cf.CFRunLoopRunInMode.restype = ctypes.c_int32
    _cf.CFRunLoopRunInMode.argtypes = [ctypes.c_void_p, ctypes.c_double, ctypes.c_bool]

    def cfstr(s):
        return _cf.CFStringCreateWithCString(None, s.encode(), 0x08000100)

    def cfnum32(v):
        val = ctypes.c_int32(v)
        return _cf.CFNumberCreate(None, 3, ctypes.byref(val))

    def prop_int(svc, k):
        ref = _iokit.IORegistryEntryCreateCFProperty(svc, cfstr(k), None, 0)
        if not ref:
            return None
        v = ctypes.c_long()
        _cf.CFNumberGetValue(ref, 4, ctypes.byref(v))
        return v.value

    shm = multiprocessing.shared_memory.SharedMemory(name=shm_name, create=False)
    buf = shm.buf
    struct.pack_into('<I', buf, 12, restart_count)

    _REPORT_CB = ctypes.CFUNCTYPE(
        None, ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p,
        ctypes.c_int, ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint8), ctypes.c_long,
    )

    decimate = [0]

    def on_report(ctx, result, sender, rtype, rid, rpt, length):
        try:
            # 22-byte reports: accel x/y/z as i32 at offsets 6,10,14
            # ~800hz native, we keep 1 in 8 -> ~100hz
            if length == 22:
                decimate[0] += 1
                if decimate[0] < 8:
                    return
                decimate[0] = 0
                data = bytes(rpt[:22])
                x = struct.unpack('<i', data[6:10])[0]
                y = struct.unpack('<i', data[10:14])[0]
                z = struct.unpack('<i', data[14:18])[0]
                shm_write_sample(buf, x, y, z)
        except Exception:
            pass

    cb_ref = _REPORT_CB(on_report)

    # wake the SPU drivers
    matching = _iokit.IOServiceMatching(b'AppleSPUHIDDriver')
    it = ctypes.c_uint()
    _iokit.IOServiceGetMatchingServices(0, matching, ctypes.byref(it))
    while True:
        svc = _iokit.IOIteratorNext(it.value)
        if not svc:
            break
        for k, v in [('SensorPropertyReportingState', 1),
                     ('SensorPropertyPowerState', 1),
                     ('ReportInterval', 1000)]:
            _iokit.IORegistryEntrySetCFProperty(svc, cfstr(k), cfnum32(v))
        _iokit.IOObjectRelease(svc)

    # find accel device: vendor page 0xFF00, usage 3
    matching = _iokit.IOServiceMatching(b'AppleSPUHIDDevice')
    it2 = ctypes.c_uint()
    _iokit.IOServiceGetMatchingServices(0, matching, ctypes.byref(it2))
    gc_roots = []
    while True:
        svc = _iokit.IOIteratorNext(it2.value)
        if not svc:
            break
        up = prop_int(svc, 'PrimaryUsagePage') or 0
        u = prop_int(svc, 'PrimaryUsage') or 0
        if (up, u) == (0xFF00, 3):
            hid = _iokit.IOHIDDeviceCreate(kCFAllocatorDefault, svc)
            if hid:
                kr = _iokit.IOHIDDeviceOpen(hid, 0)
                if kr == 0:
                    rb = (ctypes.c_uint8 * 4096)()
                    gc_roots.append(rb)
                    _iokit.IOHIDDeviceRegisterInputReportCallback(
                        hid, rb, 4096, cb_ref, None)
                    _iokit.IOHIDDeviceScheduleWithRunLoop(
                        hid, _cf.CFRunLoopGetCurrent(), kCFRunLoopDefaultMode)
        _iokit.IOObjectRelease(svc)

    gc_roots.append(cb_ref)

    while True:
        _cf.CFRunLoopRunInMode(kCFRunLoopDefaultMode, 1.0, False)
