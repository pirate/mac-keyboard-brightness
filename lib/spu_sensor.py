"""
reads accelerometer + gyroscope + lid angle + ambient light on apple silicon
via iokit hid (AppleSPUHIDDevice, Bosch BMI286 IMU)
only tested on macbook pro m3 pro
"""

import ctypes
import ctypes.util
import multiprocessing.shared_memory
import struct

# hid usage pages & usages
PAGE_VENDOR = 0xFF00
PAGE_SENSOR = 0x0020
USAGE_ACCEL = 3
USAGE_GYRO = 9
USAGE_ALS = 4
USAGE_LID = 138

# report format
IMU_REPORT_LEN = 22
IMU_DATA_OFF = 6
ALS_REPORT_LEN = 122
LID_REPORT_LEN = 3

# corefoundation type ids
CF_UTF8 = 0x08000100
CF_SINT32 = 3
CF_SINT64 = 4

# iokit / driver
REPORT_BUF_SZ = 4096
REPORT_INTERVAL_US = 1000

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
SHM_NAME_GYRO = 'vib_detect_shm_gyro'

# snapshot shm for low-rate sensors (latest value only)
#   [0..3] update_count u32  [4..7] pad  [8..N] payload
SHM_SNAP_HDR = 8
SHM_NAME_ALS = 'vib_detect_shm_als'
SHM_NAME_LID = 'vib_detect_shm_lid'
SHM_ALS_SIZE = SHM_SNAP_HDR + ALS_REPORT_LEN
SHM_LID_SIZE = SHM_SNAP_HDR + 4

ACCEL_SCALE = 65536.0
GYRO_SCALE = 65536.0


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


def shm_read_new_gyro(buf, last_total):
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
        samples.append((x / GYRO_SCALE, y / GYRO_SCALE, z / GYRO_SCALE))
    return samples, total


def shm_snap_write(buf, payload):
    buf[SHM_SNAP_HDR:SHM_SNAP_HDR + len(payload)] = payload
    cnt, = struct.unpack_from('<I', buf, 0)
    struct.pack_into('<I', buf, 0, cnt + 1)


def shm_snap_read(buf, last_count, payload_len):
    cnt, = struct.unpack_from('<I', buf, 0)
    if cnt == last_count:
        return None, cnt
    return bytes(buf[SHM_SNAP_HDR:SHM_SNAP_HDR + payload_len]), cnt


def sensor_worker(shm_name, restart_count, decimate=8, gyro_shm_name=None,
                  als_shm_name=None, lid_shm_name=None):
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
        return _cf.CFStringCreateWithCString(None, s.encode(), CF_UTF8)

    def cfnum32(v):
        val = ctypes.c_int32(v)
        return _cf.CFNumberCreate(None, CF_SINT32, ctypes.byref(val))

    def prop_int(svc, k):
        ref = _iokit.IORegistryEntryCreateCFProperty(svc, cfstr(k), None, 0)
        if not ref:
            return None
        v = ctypes.c_long()
        _cf.CFNumberGetValue(ref, CF_SINT64, ctypes.byref(v))
        return v.value

    accel_shm = multiprocessing.shared_memory.SharedMemory(name=shm_name, create=False)
    accel_buf = accel_shm.buf
    struct.pack_into('<I', accel_buf, 12, restart_count)

    gyro_buf = None
    if gyro_shm_name:
        gyro_shm = multiprocessing.shared_memory.SharedMemory(
            name=gyro_shm_name, create=False)
        gyro_buf = gyro_shm.buf

    als_buf = None
    if als_shm_name:
        als_shm = multiprocessing.shared_memory.SharedMemory(
            name=als_shm_name, create=False)
        als_buf = als_shm.buf

    lid_buf = None
    if lid_shm_name:
        lid_shm = multiprocessing.shared_memory.SharedMemory(
            name=lid_shm_name, create=False)
        lid_buf = lid_shm.buf

    _REPORT_CB = ctypes.CFUNCTYPE(
        None, ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p,
        ctypes.c_int, ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint8), ctypes.c_long,
    )

    accel_decimate_ctr = [0]

    def on_accel_report(ctx, result, sender, rtype, rid, rpt, length):
        try:
            if length == IMU_REPORT_LEN:
                accel_decimate_ctr[0] += 1
                if accel_decimate_ctr[0] < max(1, int(decimate)):
                    return
                accel_decimate_ctr[0] = 0
                data = bytes(rpt[:IMU_REPORT_LEN])
                o = IMU_DATA_OFF
                x = struct.unpack('<i', data[o:o + 4])[0]
                y = struct.unpack('<i', data[o + 4:o + 8])[0]
                z = struct.unpack('<i', data[o + 8:o + 12])[0]
                shm_write_sample(accel_buf, x, y, z)
        except Exception:
            pass

    accel_cb_ref = _REPORT_CB(on_accel_report)

    gyro_decimate_ctr = [0]
    gyro_cb_ref = None
    if gyro_buf is not None:
        def on_gyro_report(ctx, result, sender, rtype, rid, rpt, length):
            try:
                if length == IMU_REPORT_LEN:
                    gyro_decimate_ctr[0] += 1
                    if gyro_decimate_ctr[0] < max(1, int(decimate)):
                        return
                    gyro_decimate_ctr[0] = 0
                    data = bytes(rpt[:IMU_REPORT_LEN])
                    o = IMU_DATA_OFF
                    x = struct.unpack('<i', data[o:o + 4])[0]
                    y = struct.unpack('<i', data[o + 4:o + 8])[0]
                    z = struct.unpack('<i', data[o + 8:o + 12])[0]
                    shm_write_sample(gyro_buf, x, y, z)
            except Exception:
                pass

        gyro_cb_ref = _REPORT_CB(on_gyro_report)

    als_cb_ref = None
    if als_buf is not None:
        def on_als_report(ctx, result, sender, rtype, rid, rpt, length):
            try:
                if length == ALS_REPORT_LEN:
                    shm_snap_write(als_buf, bytes(rpt[:ALS_REPORT_LEN]))
            except Exception:
                pass

        als_cb_ref = _REPORT_CB(on_als_report)

    lid_cb_ref = None
    if lid_buf is not None:
        def on_lid_report(ctx, result, sender, rtype, rid, rpt, length):
            try:
                if length >= LID_REPORT_LEN:
                    data = bytes(rpt[:length])
                    if data[0] != 1:
                        return
                    angle = struct.unpack('<H', data[1:3])[0] & 0x1FF
                    shm_snap_write(lid_buf, struct.pack('<f', float(angle)))
            except Exception:
                pass

        lid_cb_ref = _REPORT_CB(on_lid_report)

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
                     ('ReportInterval', REPORT_INTERVAL_US)]:
            _iokit.IORegistryEntrySetCFProperty(svc, cfstr(k), cfnum32(v))
        _iokit.IOObjectRelease(svc)

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

        cb = None
        if (up, u) == (PAGE_VENDOR, USAGE_ACCEL):
            cb = accel_cb_ref
        elif (up, u) == (PAGE_VENDOR, USAGE_GYRO) and gyro_cb_ref is not None:
            cb = gyro_cb_ref
        elif (up, u) == (PAGE_VENDOR, USAGE_ALS) and als_cb_ref is not None:
            cb = als_cb_ref
        elif (up, u) == (PAGE_SENSOR, USAGE_LID) and lid_cb_ref is not None:
            cb = lid_cb_ref

        if cb is not None:
            hid = _iokit.IOHIDDeviceCreate(kCFAllocatorDefault, svc)
            if hid:
                kr = _iokit.IOHIDDeviceOpen(hid, 0)
                if kr == 0:
                    rb = (ctypes.c_uint8 * REPORT_BUF_SZ)()
                    gc_roots.append(rb)
                    _iokit.IOHIDDeviceRegisterInputReportCallback(
                        hid, rb, REPORT_BUF_SZ, cb, None)
                    _iokit.IOHIDDeviceScheduleWithRunLoop(
                        hid, _cf.CFRunLoopGetCurrent(), kCFRunLoopDefaultMode)
        _iokit.IOObjectRelease(svc)

    gc_roots.extend([accel_cb_ref, gyro_cb_ref, als_cb_ref, lid_cb_ref])

    while True:
        _cf.CFRunLoopRunInMode(kCFRunLoopDefaultMode, 1.0, False)
