"""Machine check and compute-tier selection (Phase 0)."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any


def _ram_gb() -> float | None:
    try:
        import psutil  # type: ignore[import-untyped]

        return round(psutil.virtual_memory().total / 2**30, 1)
    except ImportError:
        pass
    if sys.platform == "win32":
        import ctypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        st = MEMORYSTATUSEX()
        st.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))  # type: ignore[attr-defined]
        return round(st.ullTotalPhys / 2**30, 1)
    try:
        return round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2**30, 1)
    except (ValueError, OSError, AttributeError):
        return None


def _gpus() -> list[dict[str, Any]]:
    """GPUs reported by nvidia-smi (independent of the installed torch build)."""
    exe = shutil.which("nvidia-smi")
    if not exe:
        return []
    try:
        out = subprocess.run(
            [exe, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=20, check=True,
        ).stdout
    except (subprocess.SubprocessError, OSError):
        return []
    gpus = []
    for line in out.strip().splitlines():
        name, mem = (x.strip() for x in line.rsplit(",", 1))
        gpus.append({"name": name, "memory_gb": round(float(mem) / 1024, 1)})
    return gpus


def _torch_info() -> dict[str, Any]:
    try:
        import torch
    except ImportError:
        return {"installed": False}
    info: dict[str, Any] = {"installed": True, "version": torch.__version__,
                            "cuda_available": torch.cuda.is_available()}
    if torch.cuda.is_available():
        info["device"] = torch.cuda.get_device_name(0)
    return info


def _network() -> bool:
    try:
        urllib.request.urlopen("https://pypi.org/simple/", timeout=8)
        return True
    except OSError:
        return False


def choose_tier(gpus: list[dict[str, Any]]) -> tuple[int, str]:
    """Tier 0: no usable GPU (< 8 GB). Tier 1: one GPU of 8-23 GB. Tier 2: >= 24 GB or several GPUs."""
    usable = [g for g in gpus if g["memory_gb"] >= 7.5]
    if not usable:
        why = "no CUDA GPU" if not gpus else f"largest GPU has {max(g['memory_gb'] for g in gpus)} GB (< 8 GB)"
        return 0, why
    if len(usable) > 1 or max(g["memory_gb"] for g in usable) >= 23.5:
        return 2, "GPU memory >= 24 GB or several GPUs"
    return 1, "one GPU with 8-23 GB"


def machine_report(disk_path: str | Path = ".", check_network: bool = True) -> dict[str, Any]:
    gpus = _gpus()
    tier, why = choose_tier(gpus)
    du = shutil.disk_usage(disk_path)
    return {
        "os": f"{platform.system()} {platform.release()} ({platform.version()})",
        "cpu": platform.processor(),
        "cpu_logical_cores": os.cpu_count(),
        "ram_gb": _ram_gb(),
        "disk_free_gb": round(du.free / 2**30, 1),
        "python": sys.version.split()[0],
        "gpus": gpus,
        "torch": _torch_info(),
        "network": _network() if check_network else None,
        "compute_tier": tier,
        "compute_tier_reason": why,
    }
