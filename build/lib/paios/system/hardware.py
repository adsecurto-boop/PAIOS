"""Hardware detection and local-model recommendation (stdlib only).

Detection is best-effort and never raises: every probe degrades to
None/0 so the AI setup flow can always render something. The
recommendation table is a pure function over the detected numbers —
the user can always override it.
"""

import ctypes
import os
import platform
import subprocess
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class HardwareProfile:
    ram_gb: float
    cpu_cores: int
    cpu_name: str
    gpu_name: str | None
    vram_gb: float | None

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ModelChoice:
    """One local model the setup flow can offer."""

    name: str  # the Ollama tag, e.g. "qwen2.5:7b"
    label: str  # human name, e.g. "Qwen2.5 7B"
    min_ram_gb: float
    recommended: bool = False

    def as_dict(self) -> dict:
        return asdict(self)


#: The supported catalog, smallest first. Ollama tags are the identity.
MODEL_CATALOG: tuple[ModelChoice, ...] = (
    ModelChoice("qwen2.5:3b", "Qwen2.5 3B", min_ram_gb=6),
    ModelChoice("llama3.2:3b", "Llama 3.2 3B", min_ram_gb=6),
    ModelChoice("qwen2.5:7b", "Qwen2.5 7B", min_ram_gb=12),
    ModelChoice("llama3.1:8b", "Llama 3.1 8B", min_ram_gb=12),
    ModelChoice("mistral:7b", "Mistral 7B", min_ram_gb=12),
    ModelChoice("qwen2.5:14b", "Qwen2.5 14B", min_ram_gb=24),
    ModelChoice("qwen2.5:32b", "Qwen2.5 32B", min_ram_gb=40),
)


def detect_ram_gb() -> float:
    """Total physical memory in GiB (0.0 when undetectable)."""
    if os.name == "nt":
        class MemoryStatusEx(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatusEx()
        status.dwLength = ctypes.sizeof(MemoryStatusEx)
        try:
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(
                ctypes.byref(status)
            ):
                return round(status.ullTotalPhys / (1024**3), 1)
        except Exception:
            pass
        return 0.0
    try:  # POSIX
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        return round(pages * page_size / (1024**3), 1)
    except (ValueError, OSError, AttributeError):
        return 0.0


def detect_gpu() -> tuple[str | None, float | None]:
    """(gpu name, VRAM GiB) via nvidia-smi; (None, None) without one."""
    try:
        completed = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None, None
    if completed.returncode != 0 or not completed.stdout.strip():
        return None, None
    first = completed.stdout.strip().splitlines()[0]
    name, _, vram_mb = first.rpartition(",")
    try:
        return name.strip() or None, round(float(vram_mb.strip()) / 1024, 1)
    except ValueError:
        return first.strip() or None, None


def detect() -> HardwareProfile:
    gpu_name, vram_gb = detect_gpu()
    return HardwareProfile(
        ram_gb=detect_ram_gb(),
        cpu_cores=os.cpu_count() or 1,
        cpu_name=platform.processor() or platform.machine() or "unknown",
        gpu_name=gpu_name,
        vram_gb=vram_gb,
    )


def recommend_models(
    ram_gb: float, vram_gb: float | None = None
) -> list[ModelChoice]:
    """The catalog entries this machine can run, with exactly one
    marked recommended (the largest tier's preferred model). Pure —
    identical inputs, identical output."""
    # A discrete GPU effectively adds headroom; weigh it lightly.
    effective = ram_gb + (vram_gb or 0.0) / 2
    runnable = [
        choice for choice in MODEL_CATALOG if choice.min_ram_gb <= effective
    ]
    if not runnable:
        runnable = [MODEL_CATALOG[0]]  # always offer the smallest
    preferred_order = (
        "qwen2.5:14b", "qwen2.5:7b", "qwen2.5:3b"
    )
    names = {choice.name for choice in runnable}
    pick = next(
        (name for name in preferred_order if name in names),
        runnable[-1].name,
    )
    return [
        ModelChoice(
            choice.name, choice.label, choice.min_ram_gb,
            recommended=(choice.name == pick),
        )
        for choice in runnable
    ]
