// NECKTIED patcher page: step-by-step assistant with automatic camera detection.
// The patching runs in worker.js (Pyodide); this file is only the user interface.
"use strict";

const PLANNED = ["A119 V3", "A129 Plus Duo", "A129 Pro Duo", "A139 Pro / 2CH / 3CH", "T130", "WM1"];

const TEXT = {
  en: {
    tagline: "Patcher for VIOFO dash cams",
    foot1: "Unofficial, not affiliated with VIOFO. Your firmware file never leaves your computer.",
    foot2: "Time zone data", foot3: "Code MIT", pkg: "Package {0}",
    stepOf: "Step {0} of {1}: {2}",
    sCamera: "Camera", sWay: "Method", sTry: "Try it", sGet: "Get firmware", sBuild: "Build",
    back: "Back", next: "Next",
    q1: "Which camera do you have?",
    q1lead: "The model is printed on the label of the camera or on the box.",
    or: "or choose your camera",
    dropSlimH: "Already downloaded the firmware?", dropSlimP: "Drop it here and the camera is recognised.",
    dropH: "Drag the firmware file here", dropP: "e.g. {0} from your downloads folder",
    choose: "Choose file", expected: "expected: {0}, version {1}",
    famA329: "A329 family", famA229: "A229 family", famVS1: "VS1", famA119: "A119 Mini family", famPlanned: "Coming later",
    fw: "Firmware {0}", notYet: "not supported yet",
    tested: "tested on a device", experimental: "experimental",
    loading: "Loading the patcher (once, about 15 MB) …", loadPkg: "Loading NECKTIED files …",
    checking: "Checking {0} …",
    loadFail: "The patcher could not be loaded: {0}. Check your internet connection and reload the page.",
    reload: "Reload page",
    detected: "recognised", detectedTxt: "<b>{0}</b>, firmware {1} from {2}",
    q2: "How do you want to use NECKTIED?",
    q2lead: "For the {0}. {1}",
    leadTested: "This model has been tested on a device.", leadLab: "This model has only been lab-tested so far.",
    tryPill: "recommended to start", tryNo: "not possible for this model", tryH: "Try it first",
    try1: "with the memory card", try2: "firmware stays original", try3: "undo any time",
    instPill: "permanent", instH: "Install",
    inst1: "NECKTIED becomes part of the firmware", inst2File: "your firmware file is already here",
    inst2: "you need the original firmware from VIOFO", inst3: "back with the original firmware",
    sdH: "Try it with the memory card",
    sdLead: "The firmware stays original. NECKTIED starts from the memory card. Without the files on the card, everything is as before.",
    sd1: "Make sure the camera runs firmware {0} (menu › version). If not, first install this original version from VIOFO.",
    sd2: "Download {0} and unzip it.",
    sd3: "Copy <b>all</b> files to the top level of the memory card. Your videos stay.",
    sd4: "Put the card into the camera and switch it on. If it works, the version in the menu ends with {0}.",
    sdStop: "To stop: delete the NECKTIED files from the card.",
    sdNone: "There is no SD mode for the {0}. This camera can only get NECKTIED through a firmware update.",
    sdOk: "Everything works? Then you can install NECKTIED permanently.",
    sdInstall: "Install permanently now",
    getH: "Download the original firmware",
    getPanelH: "Get the original firmware from VIOFO",
    camera: "Camera", version: "Version", file: "File",
    getP: "Download exactly this version from VIOFO's firmware page. The patcher does not accept other versions.",
    toViofo: "Open VIOFO's firmware page ↗",
    haveIt: "I have the file",
    buildH: "Build the NECKTIED firmware",
    buildWithFile: "With your file {0}. It is processed in your browser only.",
    buildDrop: "Drag the downloaded file into the box. It is processed in your browser only.",
    otherCamH: "This file belongs to the {0}",
    otherCamP: "You had chosen the {0}. If your camera is a {1}, just continue with it.",
    continueWith: "Continue with the {0}", otherFile: "Choose another file",
    warnH: "Before you flash",
    warnP: "Installing modified firmware can, in the worst case, make the camera unusable. It may also void your warranty and claims against VIOFO. The safest way is to try NECKTIED in SD mode first.",
    ack: "I understand this and flash at my own risk.",
    buildBtn: "Build the NECKTIED firmware",
    progH: "Building the NECKTIED firmware for the {0}",
    progP: "Runs entirely in your browser. Takes about 10–30 seconds.",
    doneH: "Done: {0} is ready",
    doneP: "The check passed. The camera will check the file the same way.",
    save: "Save {0}",
    saveHint: "Keep the file name exactly {0}. If your browser adds something like “(1)”, rename the file.",
    checks: "Details of the check",
    howH: "How to get NECKTIED onto the camera",
    how1: "<b>Format the memory card in the camera</b>, then put it into your computer.",
    how2: "Copy {0} to the top level of the card. Do not rename it and do not add another firmware file.",
    how3: "Eject the card safely, put it into the camera and switch the camera on.",
    how4: "The camera installs the update by itself. <b>Do not cut the power during the update.</b>",
    how5Display: "Done when the NECKTIED start-up picture appears and the version in the menu ends with {0}.",
    how5: "Done when the version in the menu or app ends with {0}.",
    howBack: "Back to the original: install the original firmware from VIOFO the same way.",
    startOver: "Patch another firmware",
    errUnknownH: "This file is not a camera firmware",
    errUnknownP: "{0} is not a VIOFO firmware. The firmware file is called like {1} and comes from VIOFO's firmware page.",
    errVersionH: "Wrong firmware version",
    errVersionP: "This is a firmware for the <b>{0}</b>, but not version {1}. NECKTIED only fits exactly this version. Download it from VIOFO and try again.",
    errUnsupH: "This camera is not supported (yet)",
    errUnsupP: "{0} belongs to a camera NECKTIED does not support yet.",
    errBuildH: "The firmware could not be built",
    errBuildP: "Nothing was changed. Message: {0}",
    viofoPage: "VIOFO firmware page ↗",
    noDownload: "The download link is available on the release page.",
  },
  de: {
    tagline: "Patcher für VIOFO-Dashcams",
    foot1: "Inoffiziell, nicht mit VIOFO verbunden. Deine Firmware-Datei verlässt deinen Rechner nicht.",
    foot2: "Zeitzonendaten", foot3: "Code MIT", pkg: "Paket {0}",
    stepOf: "Schritt {0} von {1}: {2}",
    sCamera: "Kamera", sWay: "Weg", sTry: "Ausprobieren", sGet: "Firmware holen", sBuild: "Bauen",
    back: "Zurück", next: "Weiter",
    q1: "Welche Kamera hast du?",
    q1lead: "Das Modell steht auf dem Typenschild der Kamera oder auf der Verpackung.",
    or: "oder Kamera auswählen",
    dropSlimH: "Firmware-Datei schon geladen?", dropSlimP: "Hier ablegen, die Kamera wird daran erkannt.",
    dropH: "Firmware-Datei hierher ziehen", dropP: "z. B. {0} aus deinem Download-Ordner",
    choose: "Datei auswählen", expected: "erwartet: {0}, Version {1}",
    famA329: "A329-Familie", famA229: "A229-Familie", famVS1: "VS1", famA119: "A119-Mini-Familie", famPlanned: "Kommt später",
    fw: "Firmware {0}", notYet: "noch nicht unterstützt",
    tested: "am Gerät getestet", experimental: "experimentell",
    loading: "Patcher wird geladen (einmalig, etwa 15 MB) …", loadPkg: "NECKTIED-Dateien werden geladen …",
    checking: "{0} wird geprüft …",
    loadFail: "Der Patcher konnte nicht geladen werden: {0}. Prüf die Internetverbindung und lade die Seite neu.",
    reload: "Seite neu laden",
    detected: "erkannt", detectedTxt: "<b>{0}</b>, Firmware {1} aus {2}",
    q2: "Wie willst du NECKTIED nutzen?",
    q2lead: "Für die {0}. {1}",
    leadTested: "Dieses Modell ist am Gerät getestet.", leadLab: "Dieses Modell ist bisher nur im Labor getestet.",
    tryPill: "empfohlen für den Anfang", tryNo: "für dieses Modell nicht möglich", tryH: "Erst ausprobieren",
    try1: "über die Speicherkarte", try2: "Firmware bleibt original", try3: "jederzeit rückgängig",
    instPill: "dauerhaft", instH: "Installieren",
    inst1: "NECKTIED wird Teil der Firmware", inst2File: "deine Firmware-Datei ist schon da",
    inst2: "du brauchst die Original-Firmware von VIOFO", inst3: "zurück mit der Original-Firmware",
    sdH: "Ausprobieren mit der Speicherkarte",
    sdLead: "Die Firmware bleibt original. NECKTIED startet von der Speicherkarte. Ohne die Dateien auf der Karte ist alles wie vorher.",
    sd1: "Prüfen, dass die Kamera die Firmware {0} hat (Menü › Version). Sonst erst diese Original-Version von VIOFO aufspielen.",
    sd2: "{0} herunterladen und entpacken.",
    sd3: "<b>Alle</b> Dateien ins oberste Verzeichnis der Speicherkarte kopieren. Deine Videos bleiben erhalten.",
    sd4: "Karte in die Kamera, Kamera einschalten. Klappt es, endet die Version im Menü auf {0}.",
    sdStop: "Beenden: die NECKTIED-Dateien von der Karte löschen.",
    sdNone: "Für die {0} gibt es keinen SD-Modus. Die Kamera kann NECKTIED nur über ein Firmware-Update bekommen.",
    sdOk: "Läuft alles? Dann kannst du NECKTIED dauerhaft installieren.",
    sdInstall: "Jetzt dauerhaft installieren",
    getH: "Original-Firmware herunterladen",
    getPanelH: "Original-Firmware von VIOFO holen",
    camera: "Kamera", version: "Version", file: "Datei",
    getP: "Lade genau diese Version auf der Firmware-Seite von VIOFO herunter. Eine andere Version nimmt der Patcher nicht an.",
    toViofo: "Zur VIOFO-Firmware-Seite ↗",
    haveIt: "Ich habe die Datei",
    buildH: "NECKTIED-Firmware bauen",
    buildWithFile: "Mit deiner Datei {0}. Sie wird nur in deinem Browser verarbeitet.",
    buildDrop: "Zieh die heruntergeladene Datei ins Feld. Sie wird nur in deinem Browser verarbeitet.",
    otherCamH: "Diese Datei gehört zur {0}",
    otherCamP: "Ausgewählt hattest du die {0}. Wenn deine Kamera eine {1} ist, mach einfach damit weiter.",
    continueWith: "Mit {0} weitermachen", otherFile: "Andere Datei wählen",
    warnH: "Bevor du flashst",
    warnP: "Das Aufspielen veränderter Firmware kann die Kamera im schlimmsten Fall unbrauchbar machen. Außerdem können Garantieansprüche gegenüber VIOFO erlöschen. Am sichersten probierst du NECKTIED vorher im SD-Modus aus.",
    ack: "Ich habe das verstanden und flashe auf eigenes Risiko.",
    buildBtn: "NECKTIED-Firmware bauen",
    progH: "NECKTIED-Firmware für die {0} wird gebaut",
    progP: "Läuft komplett in deinem Browser. Dauert etwa 10–30 Sekunden.",
    doneH: "Fertig: {0} ist bereit",
    doneP: "Die Gegenprobe ist bestanden. Die Kamera wird die Datei genauso prüfen.",
    save: "{0} speichern",
    saveHint: "Der Dateiname muss genau {0} bleiben. Hängt dein Browser etwas wie „(1)“ an, benenne die Datei um.",
    checks: "Einzelheiten der Gegenprobe",
    howH: "So kommt NECKTIED auf die Kamera",
    how1: "Speicherkarte <b>in der Kamera formatieren</b> und am Computer einstecken.",
    how2: "{0} ins oberste Verzeichnis der Karte kopieren. Den Namen nicht ändern, keine andere Firmware-Datei dazulegen.",
    how3: "Karte sicher auswerfen, in die Kamera stecken und die Kamera einschalten.",
    how4: "Die Kamera spielt das Update von selbst ein. <b>Währenddessen nicht vom Strom trennen.</b>",
    how5Display: "Fertig, wenn das NECKTIED-Startbild erscheint und die Version im Menü auf {0} endet.",
    how5: "Fertig, wenn die Version im Menü oder in der App auf {0} endet.",
    howBack: "Zurück zum Original: die Original-Firmware von VIOFO genauso aufspielen.",
    startOver: "Weitere Firmware patchen",
    errUnknownH: "Diese Datei ist keine Kamera-Firmware",
    errUnknownP: "{0} ist keine VIOFO-Firmware. Die Firmware-Datei heißt wie {1} und kommt von der Firmware-Seite von VIOFO.",
    errVersionH: "Falsche Firmware-Version",
    errVersionP: "Das ist eine Firmware für die <b>{0}</b>, aber nicht die Version {1}. NECKTIED passt nur genau zu dieser Version. Lade sie bei VIOFO herunter und versuch es noch einmal.",
    errUnsupH: "Diese Kamera wird (noch) nicht unterstützt",
    errUnsupP: "{0} gehört zu einer Kamera, die NECKTIED noch nicht unterstützt.",
    errBuildH: "Die Firmware konnte nicht gebaut werden",
    errBuildP: "Es wurde nichts verändert. Meldung: {0}",
    viofoPage: "VIOFO-Firmware-Seite ↗",
    noDownload: "Den Download findest du auf der Release-Seite.",
  },
};

/* ---------------------------------------------------------------- basics */
const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const mono = (s) => `<span class="mono">${esc(s)}</span>`;
let lang = (() => {
  try { const l = localStorage.getItem("necktied-lang"); if (l === "en" || l === "de") return l; } catch (e) { /* no storage */ }
  return (navigator.language || "en").toLowerCase().startsWith("de") ? "de" : "en";
})();
function t(key, ...args) {
  const s = (TEXT[lang] && TEXT[lang][key]) || TEXT.en[key] || key;
  return s.replace(/\{(\d)\}/g, (_, i) => args[+i] ?? "");
}
function toast(msg) {
  const el = $("#toast"); el.textContent = msg; el.hidden = false;
  clearTimeout(toast.h); toast.h = setTimeout(() => (el.hidden = true), 3500);
}

let site = null;             // site.json
const S = { step: 1 };       // UI state: cam (BIN_NAME), file (name), fileOk, mode, err
const camByBin = (b) => site && site.cameras.find((c) => c.bin === b);
let imageUrl = null;

/* ---------------------------------------------------------------- worker */
const W = { worker: null, ready: false, failed: null, status: "pyodide", waiters: [], pending: null };
function startWorker() {
  W.worker = new Worker("worker.js");
  W.worker.onmessage = (ev) => {
    const m = ev.data;
    if (m.type === "status") { W.status = m.text; updateLoading(); }
    else if (m.type === "ready") { W.ready = true; updateLoading(); W.waiters.splice(0).forEach((f) => f()); }
    else if (m.type === "error" && m.where === "init") { W.failed = m.message; render(); }
    else if (W.pending) W.pending(m);
  };
  W.worker.onerror = (e) => { W.failed = e.message || "worker error"; render(); };
  W.worker.postMessage({ type: "init" });
}
const whenReady = () => new Promise((res) => (W.ready ? res() : W.waiters.push(res)));
function loadingLine() {
  if (W.failed) return `<div class="panel bad"><h3>${t("errBuildH")}</h3><p>${esc(t("loadFail", W.failed))}</p>
    <div class="row"><button class="btn" onclick="location.reload()">${t("reload")}</button></div></div>`;
  if (W.ready) return "";
  return `<div class="loading" id="loadline"><span class="spin"></span><span>${t(W.status === "package" ? "loadPkg" : "loading")}</span></div>`;
}
function updateLoading() {
  const el = $("#loadline");
  if (!el) return;
  if (W.ready) el.remove();
  else el.lastElementChild.textContent = t(W.status === "package" ? "loadPkg" : "loading");
}

/* identify a dropped file: resolves {bin} or {error, bin} (the worker keeps the bytes) */
async function identifyFile(file, statusEl) {
  if (statusEl) statusEl.innerHTML = `<div class="loading"><span class="spin"></span><span>${esc(t("checking", file.name))}</span></div>`;
  if (!/\.bin$/i.test(file.name) || file.size < 1e6) return { error: "unknown" };
  const buf = await file.arrayBuffer();
  await whenReady();
  return new Promise((resolve) => {
    W.pending = (m) => { W.pending = null; resolve(m.type === "identified" ? m.result : { error: "unknown" }); };
    W.worker.postMessage({ type: "identify", buf }, [buf]);
  });
}

/* ---------------------------------------------------------------- pieces */
function statusPill(c) {
  return c.tested ? `<span class="pill ok">${t("tested")}</span>` : `<span class="pill warn">${t("experimental")}</span>`;
}
function camGrid() {
  const fams = ["A329", "A229", "VS1", "A119"];
  let html = fams.map((f) => {
    const cams = site.cameras.filter((c) => c.family === f);
    if (!cams.length) return "";
    return `<div class="family"><span>${t("fam" + f)}</span><div class="cams">` + cams.map((c) =>
      `<button class="cam" type="button" data-cam="${c.bin}" aria-pressed="${c.bin === S.cam}"><b>${esc(c.name)}</b><small>${esc(t("fw", c.version))}</small></button>`
    ).join("") + `</div></div>`;
  }).join("");
  html += `<div class="family"><span>${t("famPlanned")}</span><div class="cams">` + PLANNED.map((n) =>
    `<button class="cam" type="button" disabled><b>${esc(n)}</b><small>${t("notYet")}</small></button>`).join("") + `</div></div>`;
  return html;
}
const ICON = `<svg class="icon" viewBox="0 0 48 48" aria-hidden="true"><path d="M24 30V8m0 0-8 8m8-8 8 8" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/><path d="M8 30v8a2 2 0 0 0 2 2h28a2 2 0 0 0 2-2v-8" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"/></svg>`;
function dropZone(slim, hint) {
  const input = `<input class="sr" type="file" id="file" accept=".bin,.BIN">`;
  if (slim) return `<div class="drop slim" id="drop">${ICON}<div><h3>${t("dropSlimH")}</h3><p>${t("dropSlimP")}</p></div>
    <label class="btn" for="file">${t("choose")}</label>${input}</div>`;
  return `<div class="drop" id="drop">${ICON}<h3>${t("dropH")}</h3><p>${hint}</p>
    <label class="btn primary" for="file">${t("choose")}</label>${input}</div>`;
}
function wireDrop(onFile) {
  const d = $("#drop");
  if (!d) return;
  ["dragenter", "dragover"].forEach((e) => d.addEventListener(e, (ev) => { ev.preventDefault(); d.classList.add("over"); }));
  ["dragleave", "drop"].forEach((e) => d.addEventListener(e, (ev) => { ev.preventDefault(); d.classList.remove("over"); }));
  d.addEventListener("drop", (ev) => { const f = ev.dataTransfer.files[0]; if (f) onFile(f); });
  $("#file").addEventListener("change", (ev) => { const f = ev.target.files[0]; if (f) onFile(f); });
}
function errorPanel(r, fileName) {
  const link = `<div class="row"><a href="${site.viofo}" target="_blank" rel="noopener">${t("viofoPage")}</a></div>`;
  if (r.error === "version") {
    const c = camByBin(r.bin);
    return `<div class="panel bad"><h3>${t("errVersionH")}</h3><p>${t("errVersionP", esc(c.name), mono(c.version))}</p>${link}</div>`;
  }
  if (r.error === "unsupported") return `<div class="panel bad"><h3>${t("errUnsupH")}</h3><p>${t("errUnsupP", mono(fileName))}</p></div>`;
  return `<div class="panel bad"><h3>${t("errUnknownH")}</h3><p>${t("errUnknownP", mono(fileName), mono("FWA329S.bin"))}</p>${link}</div>`;
}
function originalPanel(c) {
  return `<div class="panel"><h3>${t("getPanelH")}</h3>
    <dl class="kv"><dt>${t("camera")}</dt><dd>${esc(c.name)} ${statusPill(c)}</dd><dt>${t("version")}</dt><dd class="mono">${esc(c.version)}</dd><dt>${t("file")}</dt><dd class="mono">${esc(c.file)}</dd></dl>
    <p>${t("getP")}</p><div class="row"><a class="btn" href="${site.viofo}" target="_blank" rel="noopener">${t("toViofo")}</a></div></div>`;
}
function sdPanel(c) {
  if (!c.sd) return `<div class="panel"><h3>${t("sdH")}</h3><p>${t("sdNone", esc(c.name))}</p></div>`;
  const name = site.downloads.names[c.sd];
  const url = site.downloads[c.sd];
  const link = url ? `<a href="${url}">${esc(name)}</a>` : `${mono(name)} <span class="stepnote">(${t("noDownload")})</span>`;
  return `<div class="panel"><h3>${t("sdH")}</h3><p>${t("sdLead")}</p>
    <ol class="steps"><li><span>${t("sd1", mono(c.version))}</span></li><li><span>${t("sd2", link)}</span></li>
    <li><span>${t("sd3")}</span></li><li><span>${t("sd4", mono("-NECKTIED"))}</span></li></ol>
    <p class="stepnote">${t("sdStop")}</p></div>`;
}
function warnAck() {
  return `<div class="panel warn"><h3>${t("warnH")}</h3><p>${t("warnP")}</p>
    <label class="ack"><input type="checkbox" id="ack"> ${t("ack")}</label></div>`;
}
function howTo(c) {
  return `<div class="stack"><h3>${t("howH")}</h3><ol class="steps">
    <li><span>${t("how1")}</span></li><li><span>${t("how2", mono(c.file))}</span></li><li><span>${t("how3")}</span></li>
    <li><span>${t("how4")}</span></li><li><span>${t(c.display ? "how5Display" : "how5", mono("-NECKTIED"))}</span></li></ol>
    <p class="stepnote">${t("howBack")}</p></div>`;
}

/* ---------------------------------------------------------------- build */
function build(work, c) {
  work.innerHTML = warnAck() + `<div class="row"><button class="btn primary" id="go" type="button" disabled>${t("buildBtn")}</button></div>`;
  $("#ack").addEventListener("change", (e) => { $("#go").disabled = !e.target.checked; });
  $("#go").addEventListener("click", async () => {
    work.innerHTML = `<div class="panel prog"><h3>${t("progH", esc(c.name))}</h3><div class="bar"><i id="pbar"></i></div>
      <p id="ptext" class="stepnote"></p><p class="stepnote">${t("progP")}</p></div>`;
    await whenReady();
    W.pending = (m) => {
      if (m.type === "progress") {
        $("#pbar").style.width = Math.round(m.frac * 100) + "%";
        $("#ptext").textContent = m.text;
        return;
      }
      W.pending = null;
      if (m.type === "error") {
        work.innerHTML = `<div class="panel bad"><h3>${t("errBuildH")}</h3><p>${esc(t("errBuildP", m.message))}</p></div>`;
        return;
      }
      if (imageUrl) URL.revokeObjectURL(imageUrl);
      imageUrl = URL.createObjectURL(new Blob([m.image], { type: "application/octet-stream" }));
      S.done = true;
      work.innerHTML = `<div class="panel okp"><h3>${t("doneH", esc(m.report.file_name))}</h3><p>${t("doneP")}</p>
          <div class="row"><a class="btn primary" href="${imageUrl}" download="${esc(m.report.file_name)}">${t("save", esc(m.report.file_name))}</a></div>
          <p class="stepnote">${t("saveHint", mono(m.report.file_name))}</p>
          <details><summary class="stepnote">${t("checks")}</summary><pre class="checks">${esc(m.report.checks.join("\n"))}</pre></details></div>
        ${howTo(c)}<div class="row"><button class="btn" id="again" type="button">${t("startOver")}</button></div>`;
      $("#again").addEventListener("click", () => { Object.keys(S).forEach((k) => delete S[k]); S.step = 1; render(); });
    };
    W.worker.postMessage({ type: "patch", lang });
  });
}

/* ---------------------------------------------------------------- views */
function render() {
  const el = $("#app");
  if (!site) return;
  const c = camByBin(S.cam);
  const plan = S.mode === "sd" ? ["sCamera", "sWay", "sTry"]
    : S.fileOk ? ["sCamera", "sWay", "sBuild"] : ["sCamera", "sWay", "sGet", "sBuild"];
  const total = plan.length;
  const cur = Math.min(S.step, total);
  const stepper = `<div class="stack" style="gap:6px"><div class="stepper">${plan.map((_, i) => `<i class="${i < S.step ? "on" : ""}"></i>`).join("")}</div>
    <span class="stepnote">${t("stepOf", cur, total, t(plan[cur - 1]))}</span></div>`;
  const back = S.step > 1 ? `<button class="btn" type="button" data-back>${t("back")}</button>` : "";
  const here = plan[S.step - 1];

  if (S.step === 1) {
    el.innerHTML = `<div class="stack">${stepper}<h1>${t("q1")}</h1>${loadingLine()}
      <div id="work">${S.err ? errorPanel(S.err, S.errName) : ""}${dropZone(true)}</div>
      <div class="or">${t("or")}</div><p class="lead">${t("q1lead")}</p>${camGrid()}
      <div class="row"><button class="btn primary" type="button" data-next ${c ? "" : "disabled"}>${t("next")}</button></div></div>`;
    wireDrop(async (file) => {
      const r = await identifyFile(file, $("#work"));
      if (r.error) { S.err = r; S.errName = file.name; render(); return; }
      Object.assign(S, { err: null, cam: r.bin, file: file.name, fileOk: true, step: 2 });
      render();
    });
  } else if (S.step === 2) {
    el.innerHTML = `<div class="stack">${stepper}
      ${S.fileOk ? `<div class="panel okp found"><span class="pill ok">${t("detected")}</span><span>${t("detectedTxt", esc(c.name), mono(c.version), mono(S.file))}</span></div>` : ""}
      <h1>${t("q2")}</h1><p class="lead">${t("q2lead", esc(c.name), t(c.tested ? "leadTested" : "leadLab"))}</p>
      <div class="choices">
        <button class="choice" type="button" data-mode="sd" ${c.sd ? "" : "disabled"}><span class="pill ${c.sd ? "ok" : "bad"}">${t(c.sd ? "tryPill" : "tryNo")}</span><h3>${t("tryH")}</h3>
          <ul><li>${t("try1")}</li><li>${t("try2")}</li><li>${t("try3")}</li></ul></button>
        <button class="choice" type="button" data-mode="flash"><span class="pill muted">${t("instPill")}</span><h3>${t("instH")}</h3>
          <ul><li>${t("inst1")}</li><li>${t(S.fileOk ? "inst2File" : "inst2")}</li><li>${t("inst3")}</li></ul></button>
      </div><div class="row">${back}</div></div>`;
  } else if (here === "sTry") {
    el.innerHTML = `<div class="stack">${stepper}<h1>${t("sdH")}</h1>${sdPanel(c)}<p>${t("sdOk")}</p>
      <div class="row">${back}<button class="btn primary" type="button" data-mode="flash">${t("sdInstall")}</button></div></div>`;
  } else if (here === "sGet") {
    el.innerHTML = `<div class="stack">${stepper}<h1>${t("getH")}</h1>${originalPanel(c)}
      <div class="row">${back}<button class="btn primary" type="button" data-next>${t("haveIt")}</button></div></div>`;
  } else {
    el.innerHTML = `<div class="stack">${stepper}<h1>${t("buildH")}</h1>
      <p class="lead">${S.fileOk ? t("buildWithFile", mono(S.file)) : t("buildDrop")}</p>${loadingLine()}
      <div id="work"></div><div class="row">${back}</div></div>`;
    const work = $("#work");
    const onFile = async (file) => {
      const r = await identifyFile(file, work);
      if (r.error) { work.innerHTML = errorPanel(r, file.name) + dropZone(false, t("expected", c.file, c.version)); wireDrop(onFile); return; }
      if (r.bin !== S.cam) {                 // another camera than chosen: offer to switch
        const o = camByBin(r.bin);
        work.innerHTML = `<div class="panel warn"><h3>${t("otherCamH", esc(o.name))}</h3><p>${t("otherCamP", esc(c.name), esc(o.name))}</p>
          <div class="row"><button class="btn primary" id="sw" type="button">${t("continueWith", esc(o.name))}</button><button class="btn" id="re" type="button">${t("otherFile")}</button></div></div>`;
        $("#sw").addEventListener("click", () => { Object.assign(S, { cam: r.bin, file: file.name, fileOk: true, step: 3 }); render(); });
        $("#re").addEventListener("click", () => { work.innerHTML = dropZone(false, t("expected", c.file, c.version)); wireDrop(onFile); });
        return;
      }
      Object.assign(S, { file: file.name, fileOk: true });
      build(work, c);
    };
    if (S.fileOk) build(work, c);
    else { work.innerHTML = dropZone(false, t("expected", c.file, c.version)); wireDrop(onFile); }
  }
  el.querySelectorAll("[data-cam]").forEach((b) => b.addEventListener("click", () => {
    if (S.cam !== b.dataset.cam) { S.fileOk = false; S.file = null; }
    S.cam = b.dataset.cam; S.err = null; render();
  }));
  el.querySelectorAll("[data-mode]").forEach((b) => b.addEventListener("click", () => { S.mode = b.dataset.mode; S.step = 3; render(); }));
  el.querySelector("[data-next]")?.addEventListener("click", () => { S.step++; render(); });
  el.querySelector("[data-back]")?.addEventListener("click", () => { S.step--; if (S.step <= 2) S.mode = null; render(); });
}

function applyLang() {
  document.documentElement.lang = lang;
  document.querySelectorAll("[data-t]").forEach((e) => (e.textContent = t(e.dataset.t)));
  $("#lang").innerHTML = lang === "de" ? "EN · <b>DE</b>" : "<b>EN</b> · DE";
  if (site) $("#pkgver").textContent = t("pkg", site.version);
}
$("#lang").addEventListener("click", () => {
  lang = lang === "de" ? "en" : "de";
  try { localStorage.setItem("necktied-lang", lang); } catch (e) { /* no storage */ }
  applyLang();
  if (!S.done) render();
});

(async () => {
  applyLang();
  try {
    site = await (await fetch("site.json", { cache: "no-cache" })).json();
  } catch (e) {
    $("#app").innerHTML = `<div class="panel bad"><p>site.json: ${esc(e.message)}</p></div>`;
    return;
  }
  applyLang();
  startWorker();
  render();
})();
