#!/bin/sh
# Rebuild the QEMU virt DT for this emulator, then run the ARM64 SX1262 suite.
set -eu
if [ "$#" -ne 3 ]; then
    echo "Usage: $0 arm64-Image test-initramfs.gz WiringPi/python/tests/gpio-sim.dts" >&2
    exit 2
fi
kernel=$1
initrd=$2
gpio_dts=$3
spi_dts=$(dirname "$0")/sx1262-qemu-spi.dts
qemu=${QEMU_SYSTEM_AARCH64:-qemu-system-aarch64}
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
set -- -accel tcg -smp 1 -cpu cortex-a53 -m 256M -display none -monitor none -nic none
"$qemu" -machine "virt,dumpdtb=$tmp/base.dtb" "$@"
dtc -@ -I dts -O dtb -o "$tmp/gpio.dtbo" "$gpio_dts"
dtc -@ -I dts -O dtb -o "$tmp/spi.dtbo" "$spi_dts"
fdtoverlay -i "$tmp/base.dtb" -o "$tmp/guest.dtb" "$tmp/gpio.dtbo" "$tmp/spi.dtbo"
rc=0
timeout 90s "$qemu" -machine virt "$@" -no-reboot -serial stdio -kernel "$kernel" \
    -dtb "$tmp/guest.dtb" -initrd "$initrd" -append 'console=ttyAMA0 rdinit=/sx/init' \
    > "$tmp/console" 2>&1 || rc=$?
cat "$tmp/console"
[ "$rc" -eq 0 ] && grep -aq '^PASS-SX1262' "$tmp/console"
