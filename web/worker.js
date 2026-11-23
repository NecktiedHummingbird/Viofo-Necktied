// NECKTIED patcher worker: runs the Python patcher core under Pyodide (WebAssembly) so that
// the page stays responsive. Everything happens in this browser tab; nothing is uploaded.
//
// Messages in:  {type:"init"} | {type:"identify", buf:ArrayBuffer} | {type:"patch", lang:"en"|"de"}
// Messages out: {type:"status", text} | {type:"ready", version} | {type:"identified", result}
//               {type:"progress", frac, text} | {type:"done", image:ArrayBuffer, report}
//               {type:"error", where, message}
const PYODIDE = "https://cdn.jsdelivr.net/pyodide/v0.27.7/full/";
let py = null;
let glue = null;

async function init() {
  postMessage({ type: "status", text: "pyodide" });
  importScripts(PYODIDE + "pyodide.js");
  py = await loadPyodide({ indexURL: PYODIDE });
  await py.loadPackage("lzma");     // RTOS models (A119 V3): LZMA of the Python standard library
  const site = await (await fetch("site.json", { cache: "no-cache" })).json();
  py.FS.mkdirTree("/lib/necktied_patcher");
  for (const f of site.py_files) {
    const r = await fetch("py/" + f, { cache: "no-cache" });
    if (!r.ok) throw new Error("py/" + f + ": HTTP " + r.status);
    py.FS.writeFile("/lib/" + f, new Uint8Array(await r.arrayBuffer()));
  }
  postMessage({ type: "status", text: "package" });
  const pr = await fetch(site.package, { cache: "no-cache" });
  if (!pr.ok) throw new Error(site.package + ": HTTP " + pr.status);
  const pkg = new Uint8Array(await pr.arrayBuffer());
  py.runPython("import sys\nsys.path.insert(0, '/lib')");
  glue = py.pyimport("necktied_web");
  const version = glue.load_package(pkg);
  postMessage({ type: "ready", version });
}

self.onmessage = async (ev) => {
  const m = ev.data;
  try {
    if (m.type === "init") {
      await init();
    } else if (m.type === "identify") {
      const res = glue.identify(new Uint8Array(m.buf));
      const out = res.toJs({ dict_converter: Object.fromEntries });
      res.destroy();
      postMessage({ type: "identified", result: out });
    } else if (m.type === "patch") {
      const progress = (frac, text) => postMessage({ type: "progress", frac, text });
      const res = glue.run(m.lang, progress);
      const image = res.get(0).toJs();             // Uint8Array copy of the Python bytes
      const report = res.get(1).toJs({ dict_converter: Object.fromEntries });
      res.destroy();
      postMessage({ type: "done", image: image.buffer, report }, [image.buffer]);
    }
  } catch (e) {
    let msg = String(e && e.message || e);
    const i = msg.lastIndexOf("PatchError: ");
    if (i >= 0) msg = msg.slice(i + 12).trim();
    postMessage({ type: "error", where: m.type, message: msg });
  }
};
