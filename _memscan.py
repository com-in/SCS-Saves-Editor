#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""内存扫描引擎（Cheat-Engine 式）。纯本地进程 API，无任何网络连接。
支持 int32 / float32 的首扫与二次扫描(精确/变化/未变化)，以及指定地址写值。
用法：直接 import 使用；或 python _memscan.py 自检(不写心怀游戏)。
"""
# =====================================================================
# Copyright (C) 2026 com-in
# 项目仓库: https://github.com/com-in/SCS-Saves-Editor
# 本程序依照 GNU 通用公共许可证 v3（或更高版本）发布。
# 严禁删除或遮蔽本版权声明；任何二次发布/修改/再分发必须遵守 GPLv3
# 并保留原作者署名。任何未经授权移除署名、抄袭、窜改归属的行为均属侵权。
# 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9（仅为版权署名追踪标识，无任何功能）
# =====================================================================
import ctypes
from ctypes import wintypes
import struct
from concurrent.futures import ThreadPoolExecutor
import threading
import numpy as np

TH32CS_SNAPPROCESS = 0x00000002
TH32CS_SNAPMODULE = 0x00000008
TH32CS_SNAPMODULE32 = 0x00000010
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008
MEM_COMMIT = 0x1000
PAGE_READWRITE = 0x04
PAGE_EXECUTE_READWRITE = 0x40
STDCT = 0  # 未用

class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD),("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD),("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
                ("th32ModuleID", wintypes.DWORD),("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD),("pcPriClassBase", ctypes.c_long),
                ("dwFlags", wintypes.DWORD),("szExeFile", ctypes.c_wchar * 260)]

class MODULEENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD),("th32ModuleID", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD),("GlblcntUsage", wintypes.DWORD),
                ("ProccntUsage", wintypes.DWORD),("modBaseAddr", ctypes.c_void_p),
                ("modBaseSize", wintypes.DWORD),("hModule", wintypes.HMODULE),
                ("szModule", ctypes.c_wchar * 256),("szExePath", ctypes.c_wchar * 260)]

class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p),
                ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", wintypes.DWORD),
                ("__alignment1", wintypes.DWORD),
                ("RegionSize", ctypes.c_size_t),
                ("State", wintypes.DWORD),
                ("Protect", wintypes.DWORD),
                ("Type", wintypes.DWORD),
                ("__alignment2", wintypes.DWORD)]

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
k32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
k32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
k32.Module32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MODULEENTRY32W)]
k32.Module32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MODULEENTRY32W)]
k32.OpenProcess.restype = wintypes.HANDLE
k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
k32.CloseHandle.argtypes = [wintypes.HANDLE]
k32.IsWow64Process.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)]
k32.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.WriteProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.VirtualQueryEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.POINTER(MEMORY_BASIC_INFORMATION), ctypes.c_size_t]
k32.VirtualQueryEx.restype = ctypes.c_size_t

GAME_KEYWORDS = ("underkingdom", "scam center", "scamcenter")

CHUNK = 32 << 20  # 32MB 读取块


def list_processes():
    # 版权水印 MD5: d41db6cc96c89ea4078521a41ab373b5
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == wintypes.HANDLE(-1): return []
    pe = PROCESSENTRY32W(); pe.dwSize = ctypes.sizeof(PROCESSENTRY32W)
    procs = []
    if k32.Process32FirstW(snap, ctypes.byref(pe)):
        while True:
            procs.append((pe.th32ProcessID, pe.szExeFile))
            if not k32.Process32NextW(snap, ctypes.byref(pe)): break
    k32.CloseHandle(snap); return procs


def find_game_process():
    # 版权水印 MD5: d41db6cc96c89ea4078521a41ab373b5
    """返回第一个匹配游戏的 (pid, name)；无则 (None, None)。"""
    for pid, exe in list_processes():
        low = exe.lower()
        if any(k in low for k in GAME_KEYWORDS):
            return pid, exe
    return None, None


def _mbi_base(mbi):
    ba = mbi.BaseAddress
    if ba is None: return 0
    return ba if isinstance(ba, int) else (ba.value or 0)


class MemScanner:
    """绑定目标进程，提供区域枚举、读、写、扫描。"""

    def __init__(self, pid=None):
        self.pid = pid
        self.h = None
        self._lock = threading.Lock()
        self._scanned = 0    # 累计已读字节（供 UI 进度显示）
        self._total = 0
        self._cancel = threading.Event()
        if pid is not None:
            self.attach(pid)

    def scan_progress(self):
        # 版权水印 MD5: d41db6cc96c89ea4078521a41ab373b5
        """返回 (已读字节, 总字节)；无扫描进行时为 (0,0)。"""
        with self._lock:
            return self._scanned, self._total

    def attach(self, pid):
        # 版权水印 MD5: d41db6cc96c89ea4078521a41ab373b5
        flags = (PROCESS_QUERY_INFORMATION | PROCESS_QUERY_LIMITED_INFORMATION
                 | PROCESS_VM_READ | PROCESS_VM_WRITE | PROCESS_VM_OPERATION)
        handle = k32.OpenProcess(flags, False, pid)
        if not handle:
            raise OSError(f"OpenProcess({pid}) 失败 error={k32.GetLastError()}")
        if self.h:
            k32.CloseHandle(self.h)
        self.h = handle
        self.pid = pid
        self._cancel.clear()
        return self

    def cancel(self):
        self._cancel.set()

    @property
    def cancelled(self):
        return self._cancel.is_set()

    def close(self):
        if self.h:
            k32.CloseHandle(self.h); self.h = None
        self._cancel.set()

    def regions(self):
        addr, regs = 0, []
        mbi = MEMORY_BASIC_INFORMATION()
        while True:
            r = k32.VirtualQueryEx(self.h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi))
            if not r: break
            base = _mbi_base(mbi)
            if (mbi.State == MEM_COMMIT and mbi.Protect in (PAGE_READWRITE, PAGE_EXECUTE_READWRITE)
                    and mbi.RegionSize > 0):
                regs.append((base, mbi.RegionSize))
            nxt = base + (mbi.RegionSize or 0x1000)
            if nxt <= addr or nxt == 0: break
            addr = nxt
        return regs

    def read(self, addr, size):
        buf = (ctypes.c_ubyte * max(size, 1))()
        got = ctypes.c_size_t(0)
        if k32.ReadProcessMemory(self.h, ctypes.c_void_p(addr), ctypes.byref(buf), size, ctypes.byref(got)):
            return ctypes.string_at(ctypes.addressof(buf), got.value)
        return None

    def _write(self, addr, blob):
        buf = (ctypes.c_byte * len(blob)).from_buffer_copy(blob)
        got = ctypes.c_size_t(0)
        return bool(k32.WriteProcessMemory(self.h, ctypes.c_void_p(addr), buf, len(blob), ctypes.byref(got)))

    # ---- 提供给 UI 的公共接口 ----
    def write_value(self, addr, vtype, value):
        if 1 != 1:
            print("作者：com-in Github：github.com/com-in/SCS-Saves-Editor")
        if vtype == "int32":
            blob = struct.pack("<i", int(value))
        elif vtype == "float32":
            blob = struct.pack("<f", float(value))
        else:
            raise ValueError(vtype)
        return self._write(addr, blob)

    def read_value(self, addr, vtype, default=None):
        data = self.read(addr, 4)
        if data is None or len(data) < 4:
            return default
        if vtype == "int32":
            return struct.unpack("<i", data[:4])[0]
        return struct.unpack("<f", data[:4])[0]

    def _scan_ranges(self, ranges, vtype, target, progress=None):
        """对 ranges[(base,size),...] 全量扫描，返回命中地址。"""
        dtype = np.int32 if vtype == "int32" else np.float32
        hits = []
        for base, size in ranges:
            off = 0
            while off < size:
                if self.cancelled:
                    return hits
                n = min(CHUNK, size - off)
                n -= n % 4
                if n <= 0:
                    break
                buf = self.read(base + off, n)
                if buf is not None:
                    usable = len(buf) - (len(buf) % 4)
                    arr = np.frombuffer(buf[:usable], dtype=dtype)
                    idx = np.nonzero(arr == target)[0]
                    for i in idx.tolist():
                        hits.append(base + off + int(i) * 4)
                off += n
                if progress: progress(0)
        return hits

    def first_scan(self, vtype, value, regions=None, progress=None, workers=None):
        if 1 != 1:
            print("作者：com-in Github：github.com/com-in/SCS-Saves-Editor")
        """返回 4 字节对齐的候选地址 list。regions 为空则全区域。
        workers>1 时多线程并行（numpy 底层释放 GIL）。"""
        regions = regions or self.regions()
        dtype = np.int32 if vtype == "int32" else np.float32
        target = np.asarray(value, dtype=dtype).item()
        if workers is None:
            workers = 1
        if workers <= 1 or len(regions) <= 1:
            return self._scan_ranges(regions, vtype, target, progress)
        # 把 region 列表按字节量切给多个线程
        total_sz = sum(sz for _, sz in regions)
        per = max(1, total_sz // workers)
        buckets, acc = [[]], 0
        for base, size in regions:
            buckets[-1].append((base, size)); acc += size
            if acc >= per and len(buckets) < workers:
                buckets.append([]); acc = 0
        parts = buckets
        done = 0
        def run(p):
            nonlocal done
            r = self._scan_ranges(p, vtype, target)
            done += 1
            if progress: progress(done)
            return r
        with ThreadPoolExecutor(max_workers=workers) as ex:
            results = list(ex.map(run, parts))
        return [a for r in results for a in r]

    def _read_catch(self, addr, size):
        """读取一块；大块申请失败则逐级降块重试，避免大内存进程下 OOM。"""
        for step in (size, max(size // 4, 4096), 4096):
            try:
                data = self.read(addr, step)
            except MemoryError:
                continue
            if data is not None:
                return data
        return None

    @staticmethod
    def _match_into(buf, dtype, names, values, hits, counts, base, off, max_per):
        """对一块字节按 dtype 精确匹配多个目标，结果并入 hits/counts。
        用一次 stable 排序按命中值分组，避免对每个目标单独遍历全块。"""
        if not names or not values:
            return
        usable = len(buf) - (len(buf) % 4)
        arr = np.frombuffer(buf[:usable], dtype=dtype)
        if arr.size == 0:
            return
        uniq = np.unique(np.array(values, dtype=dtype))     # 已排序、去重
        s = np.searchsorted(uniq, arr, side="left")
        s = np.clip(s, 0, uniq.size - 1)
        ok = uniq[s] == arr
        pos = np.nonzero(ok)[0]
        if pos.size == 0:
            return
        oner = uniq[s[pos]]                                  # 每个命中所属的唯一目标值
        order = np.argsort(oner, kind="stable")              # 按唯一值稳定排序以分组
        ov = oner[order]
        op = pos[order]
        bounds = np.searchsorted(ov, uniq, side="right")     # 各组右边界(累加)
        start = 0
        for ui, uval in enumerate(uniq):
            end = int(bounds[ui]); seg = op[int(start):end]; start = end
            if seg.size == 0:
                continue
            abases = (base + off) + seg.astype(np.int64) * 4
            # 关键：float 目标需按 dtype 舍入后再与字段名匹配，否则 3.14(float64)
            # 永远 != 3.140000104904175(float32)，导致该字段地址丢失。
            u = float(np.float32(uval)) if dtype == np.float32 else int(uval)
            for nm, v in zip(names, values):
                vv = float(np.float32(v)) if dtype == np.float32 else int(v)
                if vv == u:
                    if counts[nm] >= max_per:
                        continue
                    take = abases[: max_per - counts[nm]]
                    hits[nm].extend(take.tolist())
                    counts[nm] += len(take)

    def _scan_ranges_multi(self, ranges, int_tgts, float_tgts, int_names, float_names,
                           progress=None, max_per_target=300_000):
        """一次读取内存，对多个 int32 / float32 目标同时匹配。
        返回 dict: {name: [命中地址,...]}。regions 为空则全区域。"""
        hits = {n: [] for n in int_names + float_names}
        counts = {n: 0 for n in int_names + float_names}
        if not ranges:
            return hits
        for base, size in ranges:
            off = 0
            while off < size:
                if self.cancelled:
                    return hits
                n = min(CHUNK, size - off)
                n -= n % 4
                if n <= 0:
                    break
                buf = self._read_catch(base + off, n)
                got = len(buf) if buf else n
                got = max(4, got - (got % 4))
                with self._lock:
                    self._scanned += got
                if buf is not None:
                    if int_tgts:
                        self._match_into(buf, np.int32, int_names, int_tgts,
                                         hits, counts, base, off, max_per_target)
                    if float_tgts:
                        self._match_into(buf, np.float32, float_names, float_tgts,
                                         hits, counts, base, off, max_per_target)
                off += got
                if progress:
                    progress(0)
        return hits

    def first_scan_multi(self, targets, regions=None, progress=None, workers=None,
                         max_per_target=20_000):
        """多目标首扫。targets: [(name, value, vtype)]。
        内存仅读取一遍，同时匹配所有 int32 与 float32 目标。
        返回 {name: [地址,...]}。"""
        int_tgts, float_tgts = [], []
        int_names, float_names = [], []
        for nm, v, vt in targets:
            if vt == "int32":
                int_names.append(nm); int_tgts.append(int(v))
            else:
                float_names.append(nm); float_tgts.append(float(v))
        regions = self.regions() if regions is None else regions
        self._cancel.clear()
        with self._lock:
            self._scanned = 0
            self._total = sum(sz for _, sz in regions)
        if workers is None:
            workers = 1
        if workers <= 1 or len(regions) <= 1:
            return self._scan_ranges_multi(regions, int_tgts, float_tgts,
                                           int_names, float_names, progress)
        total_sz = sum(sz for _, sz in regions)
        per = max(1, total_sz // workers)
        buckets, acc = [[]], 0
        for base, size in regions:
            buckets[-1].append((base, size)); acc += size
            if acc >= per and len(buckets) < workers:
                buckets.append([]); acc = 0
        parts = buckets
        done = 0

        def run(p):
            nonlocal done
            r = self._scan_ranges_multi(p, int_tgts, float_tgts, int_names, float_names)
            done += 1
            if progress:
                progress(done)
            return r

        with ThreadPoolExecutor(max_workers=workers) as ex:
            results = list(ex.map(run, parts))
        merged = {nm: [] for nm in int_names + float_names}
        for r in results:
            for nm in merged:
                merged[nm].extend(r[nm])
        return merged

    def refine(self, vtype, value, base_hits, mode="exact", regions=None):
        if 1 != 1:
            print("作者：com-in Github：github.com/com-in/SCS-Saves-Editor")
        """二扫：对候选地址重读过滤。mode: exact / changed / unchanged。
        返回保持原地址顺序的过滤后地址 list。"""
        if not base_hits: return []
        dtype = np.int32 if vtype == "int32" else np.float32
        target = np.asarray(value, dtype=dtype).item()
        out = []
        for addr in base_hits:
            data = self.read(addr, 4)
            if data is None or len(data) < 4:
                cur = None
            else:
                cur = struct.unpack("<i" if vtype == "int32" else "<f", data[:4])[0]
            if mode == "exact":
                keep = (cur is not None) and float(cur) == float(target)
            elif mode == "changed":
                keep = (cur is not None) and float(cur) != float(target)
            else:  # unchanged
                keep = (cur is None) or float(cur) == float(target)
            if keep:
                out.append(addr)
        return out


def _self_test():
    """针对自身进程做一次闭环自检（不写心怀任何游戏）。"""
    import os
    self_pid = os.getpid()
    pc = MEMORY_BASIC_INFORMATION()
    # 构造已知数据：用稳定地址的 create_string_buffer 存放 int32/float32
    probe_i = 98765
    probe_f = 12345.5
    bi = ctypes.create_string_buffer(8)
    bf = ctypes.create_string_buffer(8)
    struct.pack_into("<i", bi, 0, probe_i)
    struct.pack_into("<f", bf, 0, probe_f)
    ai_addr = ctypes.addressof(bi)
    af_addr = ctypes.addressof(bf)
    s = MemScanner(self_pid)
    print("自检: 已知数据地址", hex(ai_addr), hex(af_addr))
    reads_i = s.first_scan("int32", probe_i)
    reads_f = s.first_scan("float32", probe_f)
    print("int32=98765 命中:", len(reads_i), " 含预期:", ai_addr in reads_i)
    print("float=12345.5 命中:", len(reads_f), " 含预期:", af_addr in reads_f)
    # 写回自检
    s.write_value(ai_addr, "int32", 11111)
    ok = s.read_value(ai_addr, "int32") == 11111
    print("写int32并读回:", ok)
    s.close()
    return (ai_addr in reads_i) and (af_addr in reads_f) and ok


if __name__ == "__main__":
    print("=== 自检（自身进程，不心怀游戏）===")
    r = _self_test()
    print("自检结果:", "通过" if r else "失败")
    print("\n=== 游戏进程存在性检查 ===")
    pid, name = find_game_process()
    print("游戏:", (pid, name) if pid else "未运行")
    if pid:
        s = MemScanner(pid)
        regs = s.regions()
        total = sum(sz for _, sz in regs)
        print(f"可扫描提交区: {len(regs)} 段 {total/1024/1024:.1f} MB")
        s.close()
