"""NECKTIED patcher core (Linux models, groups A/B/B2), pure Python standard library.

    from necktied_patcher import Package, patch
    pkg = Package.load(open("necktied-package.zip", "rb").read())
    image, report = patch(open("FWA329S.bin", "rb").read(), pkg, variant="release")

Texts (progress, report, errors, card instructions) are English; German with
patch(..., lang="de"), set_lang("de") or the environment variable NECKTIED_LANG=de.
"""
from .core import (PatchError, patch, identify, card_instructions, apply_s99, verify_result,  # noqa: F401
                   rebuild_unchanged)
from .package import Package, PackageError, make_zip  # noqa: F401
from .i18n import set_lang, get_lang  # noqa: F401

__all__ = ["Package", "PackageError", "PatchError", "patch", "identify", "card_instructions", "make_zip",
           "rebuild_unchanged", "set_lang", "get_lang"]
