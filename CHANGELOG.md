# Release notes

Newest version first. Each release fits exactly the VIOFO firmware versions listed in its section;
download them from <https://www.viofo.com/pages/firmware>.

## v1.1 – 2026-11-23

> **Warning:** flashing modified firmware always carries a risk of making the camera unusable
> ("bricking") and may void your warranty and claims against VIOFO.

### New

- A119 V3 in the patcher (experimental: emulation and boot-loader checks only, not yet tested on a
  device). Version tag `-NECKTIED`, daylight saving time by rule, Sun HDR via the HDR timer
  (off **00:MM**, on **12:NN**), own power-on/power-off images. No time zone detection and no SD mode.
  After the update check the version; if the firmware file is still on the card, delete it.

### Changed

- A329/A229 family: the time zone from the GPS position needs only "GPS time sync" on; it no longer
  depends on the "Daylight saving time" setting. With daylight saving time off, the camera follows
  the zone and keeps standard time all year.

### Supported firmware

<!-- firmware-table -->
| Camera | Firmware | Tested on a device |
|---|---|---|
| A329S | V2.2_260815 | yes |
| A329T | V2.2_260815 | no (lab-tested) |
| A329TC | V2.2_260815 | no (lab-tested) |
| A329WW | V2.2_260815 | no (lab-tested) |
| A329 | V2.0_260812 | no (lab-tested) |
| A229 Plus | V1.5_260813 | no (lab-tested) |
| A229 Pro | V1.5_260813 | no (lab-tested) |
| A229 Pro Tele | V1.5_260813 | no (lab-tested) |
| A229 Ultra | V1.2_260813 | no (lab-tested) |
| VS1 | V1.1_260812 | no (lab-tested) |
| A119 Mini | V1.2 (2026-08-26) | no (lab-tested) |
| A119 Mini 2 | V3.2 (2026-08-26) | no (lab-tested) |
| A119 V3 | V2.6 (2024-10-31) | no (lab-tested) |
<!-- /firmware-table -->

### Known limitations

- Most cameras are lab-tested only; see [TESTED.md](TESTED.md) and please report your results
- No daylight saving time for zones with other rules (e.g. Israel, Egypt, Lebanon, Cuba, Lord Howe Island)
- A119 Mini / Mini 2: no own power-off image (the camera shows none); VS1: no display
- A119 V3: no time zone detection; daylight saving time follows the set offset (Europe, USA/Canada only)
- A129 Plus Duo, A129 Pro Duo, A139 Pro, A139 2CH/3CH, T130, WM1: planned, not yet in the patcher

## v1.0 – 2026-11-22

First public release.

> **Warning:** flashing modified firmware always carries a risk of making the camera unusable
> ("bricking") and may void your warranty and claims against VIOFO. Try the SD mode first – it does
> not change the firmware.

### New

- Automatic time zone from the GPS position
- Daylight saving time by the real rule of the zone: Europe, USA/Canada, Australia, New Zealand, Chile
- "Sun" option in the HDR menu: HDR switches on before sunset and off after sunrise
- Version tag `-NECKTIED` and own power-on/power-off images, so you see at start-up that NECKTIED is running
- Patcher for the browser and the command line: you download the original firmware from VIOFO, the
  patcher builds the NECKTIED firmware on your own computer –
  **<https://necktiedhummingbird.github.io/Viofo-Necktied/>**
- SD mode packages for the A329 family, A229 family and VS1: try NECKTIED without flashing

### Supported firmware

<!-- firmware-table -->
| Camera | Firmware | Tested on a device |
|---|---|---|
| A329S | V2.2_260815 | yes |
| A329T | V2.2_260815 | no (lab-tested) |
| A329TC | V2.2_260815 | no (lab-tested) |
| A329WW | V2.2_260815 | no (lab-tested) |
| A329 | V2.0_260812 | no (lab-tested) |
| A229 Plus | V1.5_260813 | no (lab-tested) |
| A229 Pro | V1.5_260813 | no (lab-tested) |
| A229 Pro Tele | V1.5_260813 | no (lab-tested) |
| A229 Ultra | V1.2_260813 | no (lab-tested) |
| VS1 | V1.1_260812 | no (lab-tested) |
| A119 Mini | V1.2 (2026-08-26) | no (lab-tested) |
| A119 Mini 2 | V3.2 (2026-08-26) | no (lab-tested) |
<!-- /firmware-table -->

### Known limitations

- Most cameras are lab-tested only; see [TESTED.md](TESTED.md) and please report your results
- No daylight saving time for zones with other rules (e.g. Israel, Egypt, Lebanon, Cuba, Lord Howe Island)
- A119 Mini / Mini 2: no own power-off image (the camera shows none); VS1: no display
- A119 V3, A129 Plus Duo, A129 Pro Duo, A139 Pro, A139 2CH/3CH, T130, WM1: planned, not yet in the patcher
