# Implementation and verification status

Updated 2026-10-26. This is an experimental hobby project. The previous blanket
“100% implemented / Production Ready” assessment was not supported by hardware
measurements and is withdrawn. Presence of a menu item is not proof of a working
protocol or device. License terms are in [LICENSE](LICENSE).

## Verified by host tests

81 pytest tests pass without connecting peripherals or performing radio actions.
They cover configuration injection/validation, module selection and priorities,
failed initialization, repeated loading, external module paths, shutdown after UI
and startup errors, cancellation and keyboard/mouse dialogs, SPI/I2C/GPIO cleanup,
GPIO ownership conflicts, child-process cleanup, WiFi restoration ownership,
NMEA parsing, CPU policy fixtures and DFR0528 battery fixtures. A separate
real-PTY smoke test entered text, selected the second menu item and exited the
urwid loop cleanly. No peripheral module was loaded in that smoke test.

- Hardware settings reach drivers before initialization. Disabled modules are
  not imported. Failed hardware modules are cleaned up and not presented as ready.
- Module lookup uses package IDs (`gps`, `nfc`, etc.); display-name lookup remains
  available. Unload releases event subscriptions in reverse initialization order.
- Application startup and UI execution share a cleanup scope. UI exceptions,
  startup failures and Ctrl+C do not bypass already-acquired resource cleanup.
- PN532 closes both SPI and I2C. CC1101/SX1262 cleanup still closes the bus if
  standby fails. nRF24 constructor failures release SPI and CE. GPS close is
  idempotent. GPIO cleanup addresses only owned physical pins, never all pins.
- GPIO leases reject overlapping pins and incompatible global numbering modes.
  OPi.GPIO itself must still support the actual board; this Python project does
  not automatically gain H618 support from the separate WiringPi C fork.
- Inputs and selection menus collect actual input. Esc/Cancel aborts the current
  action, including through broad module exception handlers. No default action
  is silently selected. Dialogs reuse the running screen; periodic status polling
  continues, while other event-loop alarms resume after the modal dialog closes.
- Progress updates render; module message titles/bodies use a consistent calling
  convention. Unsupported command-line mode was removed from TUI help.
- SDR streams close even after activation/read/deactivation failures. Partial USB
  gadget setup is cleaned up using configfs directory order; existing gadgets
  are not taken over or removed.
- Managed child processes are terminated/reaped on interruption. WiFi restoration
  touches only interfaces changed by that wrapper and restores their UP/DOWN
  state. It refuses to take over an interface originally in another mode.

Run the tests in an environment with the core dependencies and pytest:

```sh
python3 -m pytest -q
python3 core/main.py --config opi-zero2w-minimal.yaml --check-config
```

`main.yaml` retains the existing wiring examples. It is **not** a verified profile
for simultaneously connecting every listed device: nRF24 and CC1101 share
`spidev1.1`, and the LoRa reset and nRF24 CE examples overlap. Validation rejects
conflicting enabled modules before opening hardware. GPIO numbers are physical
header pins; `cs_pin` does not override the Linux spidev chip select. A nonexistent
`rfid` package has been removed from autoload; Proxmark remains an external-app
configuration. Use `opi-zero2w-minimal.yaml` for first TUI startup, then enable and
validate one physically connected peripheral at a time in a copied profile.

## Not yet established on hardware

| Component | Current evidence / remaining limitation |
|---|---|
| Orange Pi Zero 2W | New SD inspected offline: Armbian community 26.11.0-trunk.108, Ubuntu 26.04, kernel 6.18.57-current-sunxi64. Image has not completed first boot. |
| DFR0528 UPS | MCU identity/sample parsing and stale-data logic tested with fixtures; physical I2C adapter and readings need confirmation. No automatic shutdown. |
| CPU power | Reads kernel cpufreq policies; writes checked with fixtures. Governors/frequencies on the new board image need a runtime check. |
| CC1101 | SPI/FIFO driver exists; arbitrary pulse/RAW capture, protocol decoding, replay fidelity and Flipper compatibility are not established. |
| PN532 | Resource lifecycle covered; I2C framing/readiness and supported card operations require protocol and device tests. |
| nRF24 | Resource lifecycle covered; radio scans, CE timing and measurements unverified. |
| SX1262 / mesh | Initialization cleanup covered; GPIO numbering and hardware setup require checks. Meshtastic interoperability is not established by the local implementation. |
| GPS | NMEA parser fixtures pass; UART adapter, live fixes and exports need board tests. |
| SDR / Bluetooth / WiFi / USB gadget | Optional dependencies and menu code exist. End-to-end device operations have not been validated in this work. |
| TUI / Web UI | TUI dialogs tested with urwid widgets and fake screens, including a mouse click. Touchscreen hardware untested. Web UI authentication and demo behavior are separate outstanding work. |

No RF transmission, GPIO electrical test, real card emulation, gadget action or
successful first boot is claimed by these tests. Tasks concerning protocol
correctness, Web UI and full hardware acceptance remain separate from this
lifecycle/configuration/UI work.
