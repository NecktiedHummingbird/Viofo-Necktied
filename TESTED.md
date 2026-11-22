# NECKTIED – Test matrix

Status of every supported camera and feature. Lab tests run automatically for every release; device results come from users. Please report your result as a GitHub issue (camera, firmware version, NECKTIED version, method, what worked).

| Camera | Firmware | Version tag | Time zone from GPS | Daylight saving time | Sun HDR | Power-on/-off image |
|---|---|---|---|---|---|---|
| A329S | V2.2_260815 | ✅ | ✅ | 🧪 | ✅ | ✅ |
| A329T | V2.2_260815 | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 |
| A329TC | V2.2_260815 | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 |
| A329WW | V2.2_260815 | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 |
| A329 | V2.0_260812 | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 |
| A229 Plus | V1.5_260813 | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 |
| A229 Pro | V1.5_260813 | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 |
| A229 Pro Tele | V1.5_260813 | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 |
| A229 Ultra | V1.2_260813 | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 |
| VS1 | V1.1_260812 | 🧪 | 🧪 | 🧪 | 🧪 | — |
| A119 Mini | V1.2 (2026-08-26) | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 |
| A119 Mini 2 | V3.2 (2026-08-26) | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 |
| A119 V3 | V2.6 (2024-10-31) | ⏳ | — | ⏳ | ⏳ | ⏳ |
| A129 Plus Duo | V2.0 (2024-10-16) | ⏳ | — | ⏳ | ⏳ | ⏳ |
| A129 Pro Duo | V2.91 (2024-09-13) | ⏳ | — | ⏳ | — | ⏳ |
| A139 Pro | V1.2_240710 | ⏳ | — | ⏳ | ⏳ | — |
| A139 2CH/3CH | V1.9_240710 | ⏳ | — | ⏳ | ⏳ | — |
| T130 | V1.2_0505 | ⏳ | — | ⏳ | — | — |
| WM1 | V1.1_0602 | ⏳ | — | ⏳ | — | — |

✅ works on a real device · 🟡 partly confirmed on a device · ❌ failed on a device · 🧪 lab-tested only (no device yet) · ⏳ planned, not yet in the public patcher · — not applicable

## Lab tests per platform

- **A329S, A329T, A329TC, A329WW, A329:** self test under qemu-aarch64, image check, kernel mount test of the patched file system
- **A229 Plus, A229 Pro, A229 Pro Tele, A229 Ultra, VS1:** self test under qemu-arm, image check, kernel mount test
- **A119 Mini, A119 Mini 2:** self test under qemu-arm, image check, kernel mount test
- **Daylight saving time rules** (Europe, USA/Canada, Australia, New Zealand, Chile): every transition 2025–2045 compared with the tz database (zoneinfo)
- **A119 V3, A129 Plus Duo, A129 Pro Duo, A139 Pro, A139 2CH/3CH, T130, WM1:** emulation of the patched code (Unicorn), boot-loader checks

## Reports from real devices

| Camera | Date | Method | Reported by | Result |
|---|---|---|---|---|
| A329S | 2026-11-19 | flash | [NecktiedHummingbird](https://github.com/NecktiedHummingbird) | Version tag, time zone (UTC+1), Sun HDR (switch times matched local sunset/sunrise) and power-on image confirmed. DST transition not yet observed (next: 2027-03-28). Power-off image not yet in this build. |
| A329S | 2026-11-21 | device test | [NecktiedHummingbird](https://github.com/NecktiedHummingbird) | Power-on and power-off image confirmed. |
