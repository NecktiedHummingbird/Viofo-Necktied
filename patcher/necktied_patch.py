#!/usr/bin/env python3
"""NECKTIED patcher for the A329 family, A229 family, VS1 and A119 Mini / Mini 2.

    python3 patcher/necktied_patch.py FWA329S.bin

Download the original firmware of your camera from https://www.viofo.com/pages/firmware.
The patcher recognises the model, checks the file against the list of supported originals,
builds the NECKTIED firmware on your computer, verifies it and writes it to the folder
NECKTIED next to the original, with the file name the camera expects. For cameras that may
start NECKTIED from the memory card without flashing (experimental), it also writes the test
files to the folder NECKTIED_SD_TEST.

There are no options: every camera gets the same NECKTIED settings.
Texts are in German if your system language is German, otherwise in English.
Python 3 only (standard library), no other programs needed.
"""
import hashlib
import locale
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from necktied_patcher import Package, PackageError, PatchError, patch, set_lang  # noqa: E402
from necktied_patcher.core import TBIN_DIR  # noqa: E402
from necktied_patcher.i18n import _  # noqa: E402

PACKAGE = "necktied-package.zip"
HILFE_DE = """NECKTIED-Patcher für A329-Familie, A229-Familie, VS1 und A119 Mini / Mini 2.

    python3 patcher/necktied_patch.py FWA329S.bin

Lade die Original-Firmware deiner Kamera von https://www.viofo.com/pages/firmware. Der Patcher
erkennt das Modell, prüft die Datei gegen die Liste der unterstützten Originale, baut die
NECKTIED-Firmware auf deinem Rechner, prüft sie und schreibt sie in den Ordner NECKTIED neben
dem Original, mit dem Dateinamen, den die Kamera erwartet. Für Kameras, die NECKTIED womöglich
ohne Flashen von der Speicherkarte starten (experimentell), legt er zusätzlich die Testdateien
im Ordner NECKTIED_SD_TEST ab.

Optionen gibt es keine: Jede Kamera bekommt dieselben NECKTIED-Vorgaben.
Die Texte sind deutsch, wenn die Systemsprache Deutsch ist, sonst englisch.
Nur Python 3 (Standardbibliothek), keine weiteren Programme nötig.
"""


def system_lang():
    for var in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
        v = os.environ.get(var)
        if v:
            return "de" if v.lower().startswith("de") else "en"
    try:
        loc = locale.getlocale()[0] or ""
    except ValueError:
        loc = ""
    return "de" if loc.lower().startswith(("de", "german")) else "en"


def find_package():
    for p in (os.path.join(HERE, PACKAGE),):
        if os.path.isfile(p):
            return p
    return None


def write_checked(path, image, sha):
    """Write atomically and read back; returns False on a checksum mismatch."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(image)
    os.replace(tmp, path)
    return hashlib.sha256(open(path, "rb").read()).hexdigest() == sha


def write_tbin(folder, image, rep):
    """Group C: the same image under the test names (start without flashing, experimental)."""
    if not rep.get("tbin_names"):
        return True
    print(_("Test files (start without flashing, experimental):"))
    for n in rep["tbin_names"]:
        p = os.path.join(folder, n)
        if not write_checked(p, image, rep["image_sha256"]):
            print(_("ERROR: reading back %s gave a different checksum") % p)
            return False
        print("  " + p)
    print("\n" + rep["tbin_instructions"] + "\n")
    return True


def main(argv):
    set_lang(system_lang())
    help_text = HILFE_DE if system_lang() == "de" else __doc__
    args = argv[1:]
    if len(args) != 1 or args[0].startswith("-"):
        print(help_text)
        return 0 if args and args[0] in ("-h", "--help") else 2
    src = args[0]
    pkg_path = find_package()
    if not pkg_path:
        print(_("ERROR: %s not found next to this script. Download it from the latest release of "
                "NECKTIED on GitHub (Releases page) and put it into %s")
              % (PACKAGE, HERE))
        return 1
    try:
        pkg = Package.load(pkg_path)
        original = open(src, "rb").read()
    except (PackageError, OSError) as e:
        print(_("ERROR: %s") % e)
        return 1
    print(_("NECKTIED package %s (version %s)") % (os.path.basename(pkg_path), pkg.version))
    print(_("Original: %s\n  sha256 %s") % (src, hashlib.sha256(original).hexdigest()))

    def progress(frac, text):
        print("  [%3d%%] %s" % (round(frac * 100), text), flush=True)

    try:   # fixed NECKTIED settings – no deviation in the public patcher
        image, rep = patch(original, pkg, variant="release", logo=True, goodbye=True, compression="none",
                           progress=progress)
    except (PatchError, PackageError) as e:
        print(_("ABORTED: %s") % e)
        return 1
    print(_("Model: %s (%s, group %s)") % (rep["model"], rep["firmware"], rep["group"]))
    print(_("Verification:"))
    for c in rep["checks"]:
        print("  OK  " + c)
    out = os.path.join(os.path.dirname(os.path.abspath(src)), "NECKTIED", rep["file_name"])
    if os.path.exists(out) and os.path.samefile(out, src):
        print(_("ABORTED: output %s is the original – the original is needed for the way back") % out)
        return 1
    if not write_checked(out, image, rep["image_sha256"]):
        print(_("ERROR: reading back %s gave a different checksum") % out)
        return 1
    print(_("Written: %s\n  sha256 %s (%d bytes, %.1f s)\n") % (out, rep["image_sha256"], len(image), rep["seconds"]))
    if not write_tbin(os.path.join(os.path.dirname(os.path.abspath(src)), TBIN_DIR), image, rep):
        return 1
    print(rep["instructions"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
