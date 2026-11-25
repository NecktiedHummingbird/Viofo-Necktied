"""User texts of the patcher: English is the primary language, German is optional.

    from .i18n import _, set_lang
    set_lang("de")          # or environment NECKTIED_LANG=de (read once at import)
    _("Checking original")  -> "Original prüfen"

Every user-visible text of core.py / package.py / necktied_patch.py is written in English and
wrapped in _(); DE maps the English template (with its %-placeholders) to German. Texts
without an entry stay English. Low-level structure diagnostics (UBI/UBIFS/LZO) are English only.
"""
import os

LANGS = ("en", "de")
_state = {"lang": os.environ.get("NECKTIED_LANG", "en") if os.environ.get("NECKTIED_LANG") in LANGS else "en"}


def set_lang(lang):
    if lang not in LANGS:
        raise ValueError("language %r unknown (allowed: %s)" % (lang, ", ".join(LANGS)))
    _state["lang"] = lang


def get_lang():
    return _state["lang"]


def _(text):
    return DE.get(text, text) if _state["lang"] == "de" else text


DE = {
    # identify / S99
    "The file is not a Viofo firmware (Novatek container missing).":
        "Die Datei ist keine Viofo-Firmware (Novatek-Container fehlt).",
    "This is a different firmware version for %s. NECKTIED needs exactly %s (sha256 %s…) from "
    "https://www.viofo.com/pages/firmware.":
        "Das ist eine andere Firmware-Version für %s. NECKTIED braucht genau %s (sha256 %s…) von "
        "https://www.viofo.com/pages/firmware.",
    "This firmware (%s, sha256 %s…) is not supported.": "Diese Firmware (%s, sha256 %s…) wird nicht unterstützt.",
    "unknown": "unbekannt",
    "BIN_NAME %r does not match model %s": "BIN_NAME %r passt nicht zum Modell %s",
    "S99_Sysctl: expected replacements missing (%d instead of at least %d)":
        "S99_Sysctl: erwartete Ersetzungen fehlen (%d statt mindestens %d)",
    "S99_Sysctl: cardv start without LD_PRELOAD left": "S99_Sysctl: cardv-Start ohne LD_PRELOAD übrig",
    # patch()
    "Unknown variant %r (allowed: %s)": "Variante %r unbekannt (erlaubt: %s)",
    "Variant %r is not contained in this package": "Variante %r ist in diesem Paket nicht enthalten",
    "%s: release library missing in the package": "%s: Release-Bibliothek fehlt im Paket",
    "Unknown compression %r (allowed: none, zlib)": "Kompression %r unbekannt (erlaubt: none, zlib)",
    "Checking original": "Original prüfen",
    "Partition list %s instead of %s": "Partitionsliste %s statt %s",
    "Original fails the U-Boot check: %s": "Original besteht die U-Boot-Prüfung nicht: %s",
    "rootfs is partition id%d instead of id%d": "rootfs ist Partition id%d statt id%d",
    "rootfs partition is not CKSM+UBI": "rootfs-Partition ist kein CKSM+UBI",
    "Reading rootfs (UBI/UBIFS)": "rootfs lesen (UBI/UBIFS)",
    "zlib only for models whose original itself contains zlib nodes (group A) – use compression none here":
        "zlib nur für Modelle, deren Original selbst zlib-Knoten enthält (Gruppe A) – hier Kompression none",
    "Checking cardv": "cardv prüfen",
    "/usr/bin/cardv missing in rootfs": "/usr/bin/cardv fehlt im rootfs",
    "cardv md5 %s instead of %s – the library does not know this cardv":
        "cardv md5 %s statt %s – Bibliothek kennt dieses cardv nicht",
    "Installing NECKTIED": "NECKTIED einbauen",
    "%s missing": "%s fehlt",
    "Writing UBIFS": "UBIFS schreiben",
    "Verifying": "Gegenprobe",
    "done": "fertig",
    "unexpected volume table: %s": "unerwartete Volume-Tabelle: %s",
    "rootfs volume has unexpected properties: %s": "rootfs-Volume hat unerwartete Eigenschaften: %s",
    "rootfs volume with gaps (not made by ubinize)": "rootfs-Volume mit Lücken (nicht von ubinize erzeugt)",
    "rootfs not readable: %s": "rootfs nicht lesbar: %s",
    "Packing UBI image and firmware": "UBI-Image und Firmware packen",
    "rootfs needs %d LEBs, the volume has %d": "rootfs braucht %d LEBs, Volume hat %d",
    # verify_result()
    "U-Boot would reject the result: %s": "U-Boot würde das Ergebnis ablehnen: %s",
    "Container and all partitions pass the U-Boot checks": "Container und alle Partitionen bestehen die U-Boot-Prüfungen",
    "Partition list changed": "Partitionsliste geändert",
    "Partition id%d differs from the original": "Partition id%d weicht vom Original ab",
    "All partitions except rootfs byte-identical to the original":
        "alle Partitionen außer rootfs byte-identisch zum Original",
    "UBI geometry/volume table differs from the original": "UBI-Geometrie/Volume-Tabelle weicht vom Original ab",
    "UBI: geometry, image_seq and volume table as in the original, all header CRCs valid":
        "UBI: Geometrie, image_seq und Volume-Tabelle wie Original, alle Header-CRCs gültig",
    "Verifying: UBIFS structure": "Gegenprobe: UBIFS-Struktur",
    "new UBIFS not readable: %s": "neues UBIFS nicht lesbar: %s",
    "UBIFS structure check: %s": "UBIFS-Strukturprüfung: %s",
    "UBIFS superblock parameters differ from the original": "UBIFS-Superblock-Parameter weichen vom Original ab",
    "UBIFS: superblock parameters as in the original; index, LPT, master, log, sequence numbers and file tree "
    "consistent (%d nodes, %d LEBs)":
        "UBIFS: Superblock-Parameter wie Original; Index, LPT, Master, Log, Sequenznummern und Dateibaum "
        "konsistent (%d Knoten, %d LEBs)",
    "Verifying: file tree": "Gegenprobe: Dateibaum",
    "File tree: added %s, removed %s": "Dateibaum: hinzugefügt %s, entfernt %s",
    "File tree: changed %s instead of only %s": "Dateibaum: geändert %s statt nur %s",
    "%s: permissions/owner changed": "%s: Rechte/Eigentümer geändert",
    "%s: content not as expected": "%s: Inhalt nicht wie erwartet",
    "%s: wrong permissions/owner": "%s: Rechte/Eigentümer falsch",
    "%s: content differs from the package": "%s: Inhalt nicht wie im Paket",
    "cardv changed in the result": "cardv im Ergebnis verändert",
    "File tree: %d entries, only %s new and %s changed; all other files with identical data nodes, permissions, "
    "owners, xattrs; contents of the new files = package":
        "Dateibaum: %d Einträge, nur %s neu und %s geändert; alle übrigen Dateien mit identischen Datenknoten, "
        "Rechten, Eigentümern, xattrs; Inhalte der neuen Dateien = Paket",
    # test without flashing (group C)
    """Test without flashing (EXPERIMENTAL, %s):
  1. Copy %s from the folder %s to the root directory of the card.
     There must be NO %s on the card at the same time – that file would install the update.
  2. Eject the card cleanly, insert it into the camera and switch it on. Nothing is written to the camera.
  3. If the camera starts the test file, the NECKTIED start-up picture appears and the firmware version
     in the menu ends with -NECKTIED. During the test the camera may run with factory settings.
     If the normal VIOFO start-up picture appears, the camera does not support this test start.
  4. To end the test: delete %s from the card.
It is not yet confirmed which cameras start the test file. Please report your result (GitHub issue).""":
    """Test ohne Flashen (EXPERIMENTELL, %s):
  1. %s aus dem Ordner %s ins oberste Verzeichnis der Karte kopieren.
     Dabei darf KEINE %s auf der Karte liegen – diese Datei würde das Update einspielen.
  2. Karte sauber auswerfen, in die Kamera stecken und einschalten. In die Kamera wird nichts geschrieben.
  3. Startet die Kamera die Testdatei, erscheint das NECKTIED-Startbild und die Firmware-Version im Menü
     endet auf -NECKTIED. Während des Tests läuft die Kamera womöglich mit Werkseinstellungen.
     Erscheint das normale VIOFO-Startbild, unterstützt die Kamera diesen Teststart nicht.
  4. Test beenden: %s von der Karte löschen.
Welche Kameras die Testdatei starten, ist noch nicht bestätigt. Bitte melde dein Ergebnis (GitHub-Issue).""",
    "Test files (start without flashing, experimental):": "Testdateien (Start ohne Flashen, experimentell):",
    # card instructions
    "tested on a device": "auf dem Gerät geprüft",
    "ONLY TESTED LOCALLY – not yet tested on a device for this model":
        "NUR LOKAL GEPRÜFT – auf diesem Modell noch nicht auf einem Gerät getestet",
    """SD card instructions (%s, %s):
  1. Format the SD card in the camera (or FAT32/exFAT), then copy %s to the root directory
     of the card on the computer (exactly this file name, no other firmware files).
  2. Eject the card cleanly.
  3. Insert the card into the camera and switch it on. The camera installs the update while starting up.
     Do NOT disconnect the power during the update.
  4. Afterwards %s must have disappeared from the card (the camera deletes it after the start).
Way back: the same with the original from https://www.viofo.com/pages/firmware (%s, sha256 %s…).
Status of this model: %s.""": """Kartenanleitung (%s, %s):
  1. SD-Karte in der Kamera formatieren (oder FAT32/exFAT), dann am Rechner %s ins
     Hauptverzeichnis der Karte kopieren (genau dieser Dateiname, keine anderen Firmware-Dateien).
  2. Karte sauber auswerfen.
  3. Karte in die Kamera, Kamera einschalten. Die Kamera spielt das Update beim Hochfahren ein.
     Während des Updates NICHT vom Strom trennen.
  4. Danach muss %s von der Karte verschwunden sein (die Kamera löscht sie nach dem Start).
Rückweg: dasselbe mit dem Original von https://www.viofo.com/pages/firmware (%s, sha256 %s…).
Status dieses Modells: %s.""",
    # package.py
    "Package is not a valid zip file": "Paket ist keine gültige Zip-Datei",
    "manifest.json missing in the package": "manifest.json fehlt im Paket",
    "unknown package format %r/%r": "unbekanntes Paketformat %r/%r",
    "File %s missing in the package": "Datei %s fehlt im Paket",
    "File %s is damaged (checksum)": "Datei %s ist beschädigt (Prüfsumme)",
    "files not listed in the manifest: %s": "nicht im Manifest aufgeführte Dateien: %s",
    "%s: group %s missing in the package": "%s: Gruppe %s fehlt im Paket",
    "%s: file %s missing in the manifest": "%s: Datei %s fehlt im Manifest",
    # necktied_patch.py (CLI)
    "%s needs a value": "%s braucht einen Wert",
    "--goodbye: 'on' or 'off' (not %r)": "--ausschaltbild: 'an' oder 'aus' (nicht %r)",
    "Unknown arguments: %s\n": "Unbekannte Argumente: %s\n",
    "ERROR: NECKTIED package not found (--package necktied-package.zip)":
        "FEHLER: NECKTIED-Paket nicht gefunden (--paket necktied-package.zip)",
    "ERROR: package %s: %s": "FEHLER: Paket %s: %s",
    "ERROR: %s": "FEHLER: %s",
    "ERROR: %s not found next to this script. Download it from the latest release of "
    "NECKTIED on GitHub (Releases page) and put it into %s":
        "FEHLER: %s liegt nicht neben diesem Skript. Aus dem neuesten Release von NECKTIED auf "
        "GitHub (Release-Seite) laden und nach %s legen",
    "Model: %s (%s, group %s)": "Modell: %s (%s, Gruppe %s)",
    "NECKTIED package %s (version %s)": "NECKTIED-Paket %s (Version %s)",
    "Original: %s\n  sha256 %s": "Original: %s\n  sha256 %s",
    "ABORTED: %s": "ABGEBROCHEN: %s",
    "Model: %s (%s, group %s), variant %s": "Modell: %s (%s, Gruppe %s), Variante %s",
    "Goodbye picture: %s": "Ausschaltbild: %s",
    "own picture": "eigenes Bild",
    "same as the boot picture (this model has no picture of its own when switching off)":
        "wie Einschaltbild (Modell ohne eigenes Ausschaltbild)",
    "same as the boot picture": "wie Einschaltbild",
    "Changes: new %s; changed %s": "Änderungen: neu %s; geändert %s",
    "Verification:": "Gegenprobe:",
    "ABORTED: output %s is the original – the original is needed for the way back":
        "ABGEBROCHEN: Ausgabe %s ist das Original – das Original wird für den Rückweg gebraucht",
    "NOTE: The camera expects the file name %s – rename it before copying.":
        "HINWEIS: Die Kamera erwartet den Dateinamen %s – vor dem Kopieren umbenennen.",
    "ERROR: reading back %s gave a different checksum": "FEHLER: Rücklesen von %s ergab eine andere Prüfsumme",
    "Written: %s\n  sha256 %s (%d bytes, %.1f s)\n": "Geschrieben: %s\n  sha256 %s (%d Byte, %.1f s)\n",
    # rtos.py (group C, A119 V3)
    "MODELEXT without partition table": "MODELEXT ohne Partitionstabelle",
    "Picture %s too big for the slot (%d > %d bytes)": "Bild %s zu groß für den Platz (%d > %d Byte)",
    "Partition layout differs from the supported firmware": "Partitionsaufbau weicht von der unterstützten Firmware ab",
    "Unpacking RTOS": "RTOS entpacken",
    "RTOS not readable: %s": "RTOS nicht lesbar: %s",
    "RTOS differs from the supported firmware": "RTOS weicht von der unterstützten Firmware ab",
    "RTOS checksum of the original is wrong": "RTOS-Prüfsumme des Originals stimmt nicht",
    "%s: address %#x outside the RTOS": "%s: Adresse %#x außerhalb des RTOS",
    "%s: overlaps another change": "%s: überschneidet sich mit einer anderen Änderung",
    "A change hits the RTOS checksum": "Eine Änderung trifft die RTOS-Prüfsumme",
    "Compressing RTOS (LZMA)": "RTOS komprimieren (LZMA)",
    "Packing firmware": "Firmware packen",
    "Container and all partitions pass the checks of the U-Boot (GUID, checksums, sizes, flash partitions)":
        "Container und alle Partitionen bestehen die Prüfungen des U-Boot (GUID, Prüfsummen, Größen, "
        "Flash-Partitionen)",
    "All partitions except the RTOS byte-identical to the original":
        "Alle Partitionen außer dem RTOS byte-identisch zum Original",
    "new RTOS not readable: %s": "neues RTOS nicht lesbar: %s",
    "new RTOS: size or checksum wrong": "neues RTOS: Größe oder Prüfsumme falsch",
    "%s: not written as in the package": "%s: nicht wie im Paket geschrieben",
    "new RTOS: unexpected change at %#x": "neues RTOS: unerwartete Änderung bei %#x",
    "RTOS unpacked again: checksum valid, only the intended bytes changed (%d bytes in %d changes)":
        "RTOS erneut entpackt: Prüfsumme gültig, nur die beabsichtigten Bytes geändert (%d Byte in %d Änderungen)",
    "Changes in the RTOS: %s": "Änderungen im RTOS: %s",
    """SD card instructions (%s, %s):
  1. Format the SD card in the camera (or FAT32/exFAT), then copy %s to the root directory
     of the card on the computer (exactly this file name, no other firmware files).
  2. Eject the card cleanly.
  3. Insert the card into the camera and switch it on. The camera installs the update while starting up.
     Do NOT disconnect the power during the update.
  4. Check that the firmware version in the menu ends with -NECKTIED, then delete %s from the card
     if it is still there (otherwise the camera may install it again at every start).
Way back: the same with the original from https://www.viofo.com/pages/firmware (%s, sha256 %s…).
Status of this model: %s.""": """Kartenanleitung (%s, %s):
  1. SD-Karte in der Kamera formatieren (oder FAT32/exFAT), dann am Rechner %s ins
     Hauptverzeichnis der Karte kopieren (genau dieser Dateiname, keine anderen Firmware-Dateien).
  2. Karte sauber auswerfen.
  3. Karte in die Kamera, Kamera einschalten. Die Kamera spielt das Update beim Hochfahren ein.
     Während des Updates NICHT vom Strom trennen.
  4. Prüfen, dass die Firmware-Version im Menü auf -NECKTIED endet, dann %s von der Karte löschen,
     falls sie noch dort liegt (sonst spielt die Kamera sie womöglich bei jedem Start erneut ein).
Rückweg: dasselbe mit dem Original von https://www.viofo.com/pages/firmware (%s, sha256 %s…).
Status dieses Modells: %s.""",
}
