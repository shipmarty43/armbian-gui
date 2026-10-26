# Reliability and hardware bring-up changes

A failed driver or UI startup previously left resources open; global GPIO cleanup
could reset another module's pins. Input and selection helpers silently returned
defaults. Module loading also ignored conflicts and could show failed hardware as
ready.

The change adds scoped application/driver cleanup, per-driver GPIO ownership,
configuration conflict checks, real input/selection dialogs with cancellation,
and package-ID module lookup. Only WiFi interfaces changed by this process are
restored, and managed child processes are reaped on errors or interruption.

Validation: 81 pytest tests passed both on the host and natively on Orange Pi
Zero 2W (kernel 6.18.57, Python 3.14.4), including failure injection,
configuration, keyboard/mouse input and shutdown. Native PTY checks covered
dialogs, full minimal-profile startup and clean exit; headless SIGINT cleanup
and live CPUFreq discovery also passed. No peripheral operations were performed.
See [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) for exact evidence and
remaining hardware/protocol limitations. Earlier installation and production
readiness claims in this file were unverified; their original text remains in Git
history. The current source is experimental.
