"""NECKTIED patch package: our own files only (libraries, time zone raster, boot logos, goodbye
pictures) plus a
JSON manifest with the supported stock firmwares (identified by sha256, never contained).

Container: a zip file (or a dict {name: bytes}) with
    manifest.json
    files/<group>/necktied.so, files/<group>/necktied_log.so, files/<group>/necktied_tz.bin
    files/logo/<logo>.jpg
    files/goodbye/<goodbye>.jpg        (optional: picture shown when switching off)
Manifest (format_version 1):
    {"format": "necktied-patch-package", "format_version": 1, "version": "...",
     "groups": {"A": {"variants": {"release": "files/A/necktied.so", "diagnose": "files/A/necktied_log.so"},
                      "tz": "files/A/necktied_tz.bin",
                      "s99": {"path": "/etc/init.d/S99_Sysctl", "command": "cardv ",
                              "prefix": "LD_PRELOAD=/usr/lib/necktied.so ", "indent": false,
                              "min_count": 2, "all_starts": false}}, ...},
     "install": {"lib": ["/usr/lib/necktied.so", 493], "tz": ["/usr/lib/necktied_tz.bin", 420],
                 "logo": ["/usr/lib/necktied_logo.jpg", 420],
                 "goodbye": ["/usr/lib/necktied_goodbye.jpg", 420]},
     "edition": "private" | "public",
     "models": {"FWA329S": {"model": "A329S", "version": "VIOFO_A329S_V2.2_260815", "verified": true,
                            "sha256": "...", "cardv_md5": "...", "group": "A", "rootfs_id": 7,
                            "part_ids": [1, 3, 4, 6, 7, 9], "logo": "files/logo/necktied_logo.jpg" | null,
                            "goodbye": "files/goodbye/necktied_goodbye_512x384.jpg" | null}},
    "goodbye" (model and install entry) is optional: older packages without it are still valid.
     "files": {"files/A/necktied.so": {"sha256": "...", "size": 55728}, ...}}
Format version 2 adds RTOS groups (group C, static patch of the RTOS image, rtos.py):
    "groups": {"C": {"kind": "rtos", "description": "...", "variants": {"release": "rtos"}}}
    "models": {"FWA119V3": {..., "group": "C", "size": <stock file size>,
                            "rtos": "files/C/FWA119V3.json",            patch description (rtos.py)
                            "logo": "files/logo/...rtos.jpg", "goodbye": "files/goodbye/...rtos.jpg"}}
"""
import hashlib
import io
import json
import zipfile

from .i18n import _

FORMAT = "necktied-patch-package"
FORMAT_VERSION = 2          # 2: groups of kind "rtos" (group C); version 1 packages are still read
FORMAT_VERSIONS = (1, 2)
VARIANTS = ("release", "diagnose")


class PackageError(ValueError):
    pass


class Package:
    def __init__(self, manifest, files):
        self.manifest = manifest
        self.files = files
        self._check()

    @classmethod
    def load(cls, src):
        """src: zip bytes, a path to a zip file, or {name: bytes}."""
        if isinstance(src, dict):
            files = dict(src)
        else:
            if isinstance(src, str):
                with open(src, "rb") as f:
                    src = f.read()
            try:
                z = zipfile.ZipFile(io.BytesIO(src))
            except zipfile.BadZipFile:
                raise PackageError(_("Package is not a valid zip file"))
            files = {n: z.read(n) for n in z.namelist() if not n.endswith("/")}
        if "manifest.json" not in files:
            raise PackageError(_("manifest.json missing in the package"))
        manifest = json.loads(files.pop("manifest.json").decode("utf-8"))
        return cls(manifest, files)

    def _check(self):
        m = self.manifest
        if m.get("format") != FORMAT or m.get("format_version") not in FORMAT_VERSIONS:
            raise PackageError(_("unknown package format %r/%r") % (m.get("format"), m.get("format_version")))
        for name, meta in m["files"].items():
            data = self.files.get(name)
            if data is None:
                raise PackageError(_("File %s missing in the package") % name)
            if len(data) != meta["size"] or hashlib.sha256(data).hexdigest() != meta["sha256"]:
                raise PackageError(_("File %s is damaged (checksum)") % name)
        extra = set(self.files) - set(m["files"])
        if extra:
            raise PackageError(_("files not listed in the manifest: %s") % sorted(extra))
        for b, mod in m["models"].items():
            g = m["groups"].get(mod["group"])
            if g is None:
                raise PackageError(_("%s: group %s missing in the package") % (b, mod["group"]))
            if "release" not in g["variants"]:
                raise PackageError(_("%s: release library missing in the package") % b)
            pics = ([mod["logo"]] if mod.get("logo") else []) + ([mod["goodbye"]] if mod.get("goodbye") else [])
            if g.get("kind") == "rtos":
                refs = [mod.get("rtos")] + pics
            else:
                refs = [g["tz"]] + list(g["variants"].values()) + pics
            for r in refs:
                if r not in m["files"]:
                    raise PackageError(_("%s: file %s missing in the manifest") % (b, r))

    @property
    def version(self):
        return self.manifest.get("version", "?")

    def models(self):
        return self.manifest["models"]

    def model_by_sha256(self, sha):
        for b, mod in self.manifest["models"].items():
            if mod["sha256"] == sha:
                return b, mod
        return None, None

    def group(self, name):
        return self.manifest["groups"][name]

    def file(self, name):
        return self.files[name]


def make_zip(manifest, files):
    """Deterministic zip (sorted names, fixed time stamps)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        def add(name, data):
            zi = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            z.writestr(zi, data)
        add("manifest.json", json.dumps(manifest, indent=1, sort_keys=True, ensure_ascii=False).encode() + b"\n")
        for n in sorted(files):
            add(n, files[n])
    return buf.getvalue()
