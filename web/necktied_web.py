"""Glue between the web page (web/worker.js, Pyodide) and the patcher core (necktied_patcher).

The page never sends the firmware anywhere: the worker hands the bytes to these functions in
WebAssembly CPython inside the browser. The NECKTIED settings are fixed (release library, boot
logo, goodbye picture) – the same as the public command line patcher.
"""
import hashlib

from necktied_patcher import Package, PackageError, PatchError, patch, set_lang
from necktied_patcher import nvtpack as nv
from necktied_patcher.core import rtos_name

_pkg = None
_orig = None


def load_package(data):
    global _pkg
    _pkg = Package.load(bytes(data))
    return _pkg.version


def identify(data):
    """dict: {"bin": BIN_NAME} for a supported original (kept for patch()), otherwise
    {"error": "unknown" | "version" | "unsupported", "bin": BIN_NAME or None}."""
    global _orig
    _orig = None
    data = bytes(data)
    if data[:16] != nv.NVTPACK_GUID:
        return {"error": "unknown", "bin": None}
    try:
        name = nv.bin_name(data)
    except Exception:
        name = None
    b, mod = _pkg.model_by_sha256(hashlib.sha256(data).hexdigest())
    if mod is None:
        name = name or rtos_name(data, _pkg)
        return {"error": "version" if name in _pkg.models() else "unsupported", "bin": name}
    if _pkg.group(mod["group"]).get("kind") != "rtos" and name != b:
        return {"error": "unsupported", "bin": name}
    _orig = data
    return {"bin": b}


def run(lang, progress):
    """Build the NECKTIED image of the identified original. Returns (image, report) or raises."""
    if _orig is None:
        raise PatchError("no identified firmware")
    set_lang(lang)
    image, rep = patch(_orig, _pkg, variant="release", logo=True, goodbye=True, compression="none",
                       progress=lambda f, text: progress(f, text))
    report = {k: rep[k] for k in ("bin_name", "file_name", "model", "firmware", "checks", "seconds")}
    report["tbin_names"] = rep.get("tbin_names", [])     # group C: test start without flashing
    return image, report


__all__ = ["load_package", "identify", "run", "PatchError", "PackageError"]
