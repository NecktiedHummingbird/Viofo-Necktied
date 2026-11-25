#!/usr/bin/env python3
"""Assemble the NECKTIED patcher web page (GitHub Pages) from this repository and a release package.

    python3 -I web/build_site.py OUTDIR --package necktied-package.zip [--repo OWNER/NAME]

OUTDIR receives:
  index.html, style.css, app.js, worker.js      the page (web/)
  py/necktied_web.py, py/necktied_patcher/*.py  the patcher core, run in the browser by Pyodide
  necktied-package.zip                          NECKTIED's own files (from the GitHub release)
  logo.jpg                                      public logo (assets/)
  site.json                                     cameras, package version, release links

--repo names the GitHub repository for the release download links (the Pages workflow passes
${{ github.repository }}). Python standard library only.
"""
import json
import os
import re
import shutil
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOP = os.path.dirname(HERE)
PAGE = ["index.html", "style.css", "app.js", "worker.js"]
SD = {"A": "NECKTIED_SD_A.zip", "B": "NECKTIED_SD_B.zip"}      # groups with an SD start path
FAMILY = {"A": "A329", "B": "A229"}            # other groups: A119 by name, everything else "Other"


def short_version(v):
    m = re.search(r"[_.](V\d+\.\d+)\.(\d{4})(\d\d)(\d\d)$", v)
    if m:
        return "%s (%s-%s-%s)" % m.groups()
    m = re.search(r"_(V\d+\.\d+_\d{6})$", v)
    return m.group(1) if m else v


def find_logo():
    for p in (os.path.join(TOP, "assets", "necktied_logo_public_b_320x240.jpg"),
              os.path.join(TOP, "necktied", "assets", "public", "necktied_logo_public_b_320x240.jpg")):
        if os.path.isfile(p):
            return p
    raise SystemExit("Logo nicht gefunden (assets/necktied_logo_public_b_320x240.jpg)")


def cameras(manifest):
    out = []
    for b, m in manifest["models"].items():
        fam = "Other" if m["model"] == "VS1" else "A119" if m["model"].startswith("A119") \
            else FAMILY.get(m["group"], "Other")
        out.append(dict(bin=b, name=m["model"], file=b + ".bin", version=short_version(m["version"]),
                        tested=bool(m.get("verified")), display=bool(m.get("logo")),
                        sd=m["group"] if m["group"] in SD else None, family=fam, rtos=m["group"] == "C",
                        tbin=list(m.get("tbin") or [])))   # test files built in the browser (experimental)
    order = {"A329": 0, "A229": 1, "A119": 2, "Other": 3}
    out.sort(key=lambda c: (order.get(c["family"], 9), c["bin"] != "FWA329S", c["rtos"], c["name"]))
    return out


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    opt = lambda k, d=None: argv[argv.index(k) + 1] if k in argv else d   # noqa: E731
    if not args or "--package" not in argv:
        print(__doc__)
        return 2
    out, pkg_path, repo = args[0], opt("--package"), opt("--repo", "")
    with zipfile.ZipFile(pkg_path) as z:
        manifest = json.loads(z.read("manifest.json"))
    if manifest.get("edition") != "public":
        raise SystemExit("%s ist kein öffentliches Paket (edition %r)" % (pkg_path, manifest.get("edition")))
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(os.path.join(out, "py", "necktied_patcher"))
    for f in PAGE:
        shutil.copyfile(os.path.join(HERE, f), os.path.join(out, f))
    py_files = ["necktied_web.py"]
    shutil.copyfile(os.path.join(HERE, "necktied_web.py"), os.path.join(out, "py", "necktied_web.py"))
    core = os.path.join(TOP, "patcher", "necktied_patcher")
    for f in sorted(os.listdir(core)):
        if f.endswith(".py"):
            shutil.copyfile(os.path.join(core, f), os.path.join(out, "py", "necktied_patcher", f))
            py_files.append("necktied_patcher/" + f)
    shutil.copyfile(pkg_path, os.path.join(out, "necktied-package.zip"))
    shutil.copyfile(find_logo(), os.path.join(out, "logo.jpg"))
    rel = "https://github.com/%s/releases/latest" % repo if repo else ""
    site = dict(version=manifest.get("version", "?"), package="necktied-package.zip", py_files=py_files,
                cameras=cameras(manifest), releases=rel,
                downloads={k: (rel + "/download/" + v if rel else "") for k, v in SD.items()} | {"names": SD},
                viofo="https://www.viofo.com/pages/firmware")
    with open(os.path.join(out, "site.json"), "w", encoding="utf-8") as f:
        json.dump(site, f, indent=1, ensure_ascii=False)
    open(os.path.join(out, ".nojekyll"), "w").close()
    print("Seite in %s: %d Kameras, Paket %s" % (out, len(site["cameras"]), site["version"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
