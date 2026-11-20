"""Compile the Waveshare overlay, merge a stock DTB and exercise runtime route discovery."""
import argparse
from pathlib import Path
import struct
import subprocess
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.sx1262_spi import find_spi


def check(stock, output):
    source = Path(__file__).resolve().parents[1] / 'hardware/overlays/opi-zero2w-sx1262.dts'
    with TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        overlay, merged = tmp / 'hat.dtbo', tmp / 'merged.dtb'
        subprocess.run(['dtc', '-@', '-I', 'dts', '-O', 'dtb', '-o', overlay, source], check=True)
        subprocess.run(['fdtoverlay', '-i', stock, '-o', merged, overlay], check=True)
        def prop(blob, node, key, kind='s'):
            return subprocess.check_output(['fdtget', '-t', kind, blob, node, key], text=True).split()
        compatible = prop(stock, '/', 'compatible')
        if not {'xunlong,orangepi-zero2w', 'allwinner,sun50i-h618'} <= set(compatible):
            raise ValueError('Expected the Zero 2W/H618 base DTB')
        spi = '/soc/spi@5011000'
        node = spi + '/radio@0'
        if (prop(merged, spi, 'status') != ['okay'] or prop(merged, node, 'spi-max-frequency', 'u') != ['16000000']
                or prop(merged, node, 'compatible') != ['semtech,sx1262', 'armbian,spi-dev']):
            raise ValueError('Unexpected SPI endpoint after merge')
        # Materialize the merged DT properties exactly as exposed in sysfs.
        files = tmp / 'firmware/devicetree/base'
        files.mkdir(parents=True)
        def copy_prop(path, key, kind):
            values = prop(merged, path, key, kind)
            data = (b''.join(v.encode() + b'\0' for v in values) if kind == 's' else
                    b''.join(struct.pack('>I', int(v)) for v in values))
            dest = files / path.lstrip('/')
            dest.mkdir(parents=True, exist_ok=True)
            (dest / key).write_bytes(data)
        for path, key, kind in (
            (spi, 'cs-gpios', 'u'), (spi, 'pinctrl-0', 'u'), (node, 'reg', 'u'),
            (node, 'compatible', 's'), ('/soc/pinctrl@300b000', 'phandle', 'u'),
            ('/soc/pinctrl@300b000/spi1-pins', 'phandle', 'u'),
            ('/soc/pinctrl@300b000/spi1-pins', 'pins', 's'),
            ('/soc/pinctrl@300b000/spi1-pins', 'function', 's'),
        ):
            copy_prop(path, key, kind)
        children = subprocess.check_output(['fdtget', '-l', merged, spi], text=True).split()
        for child in children:
            path = spi + '/' + child
            keys = subprocess.check_output(['fdtget', '-p', merged, path], text=True).split()
            for key in ('status', 'reg', 'spi-cs-high'):
                if key in keys:
                    copy_prop(path, key, 's' if key == 'status' else 'u')
        endpoint = tmp / 'class/spidev/spidev9.0/device'
        endpoint.mkdir(parents=True)
        (endpoint / 'of_node').symlink_to(files / node.lstrip('/'))
        if find_spi('auto', 0, sysfs=tmp) != (9, 0):
            raise ValueError('Merged DT rejected by runtime detection')
        if output:
            output.write_bytes(overlay.read_bytes())
        print('PASS H618 SPI1 PH6/PH7/PH8, kernel CS0 on PI3 active-low, 16 MHz ceiling, automatic route discovery')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stock', type=Path)
    parser.add_argument('--dtbo', type=Path)
    args = parser.parse_args()
    check(args.stock, args.dtbo)
