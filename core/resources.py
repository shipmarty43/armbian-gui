"""Small lifecycle helpers for partially initialized hardware drivers."""
from contextlib import contextmanager
from functools import wraps
import logging
import threading


def close_attributes(owner, *names):
    """Detach first, then try every close even when one device has disappeared."""
    for name in names:
        resource = getattr(owner, name, None)
        setattr(owner, name, None)
        if resource is not None:
            try:
                resource.close()
            except Exception:
                logging.getLogger(__name__).exception('Closing %s failed', name)


def cleanup_on_failure(method):
    """Close failed constructors and false/exceptional initialize() results."""
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        success = False
        try:
            result = method(self, *args, **kwargs)
            success = result is not False
            return result
        finally:
            if not success:
                self.close()
    return wrapped


class GpioLease:
    """Own only this driver's BOARD pins; never reset another driver's pins.

    OPi.GPIO has process-global numbering. All users here agree on physical
    header numbers. This registry detects in-process conflicts; kernel ownership
    and H618 board support still depend on the installed GPIO implementation.
    """
    _owners = {}
    _lock = threading.RLock()

    def __init__(self, gpio):
        self.gpio = gpio
        self.pins = []

    def setup(self, pin, direction, initial=None):
        if not isinstance(pin, int) or isinstance(pin, bool) or pin <= 0:
            raise ValueError('GPIO pin must be a positive physical header number')
        key = (id(self.gpio), pin)
        with self._lock:
            if key in self._owners and self._owners[key] is not self:
                raise RuntimeError(f'GPIO physical pin {pin} is already owned by another driver')
            if pin in self.pins:
                raise RuntimeError(f'GPIO physical pin {pin} requested twice')
            mode = self.gpio.getmode()
            if mode is not None and mode != self.gpio.BOARD:
                raise RuntimeError('GPIO numbering is not BOARD; refusing a global mode change')
            if mode is None:
                self.gpio.setmode(self.gpio.BOARD)
            self._owners[key] = self
            self.pins.append(pin)
            try:
                self.gpio.setup(pin, direction)
                if initial is not None:
                    self.gpio.output(pin, initial)
            except BaseException:
                self._release(pin)
                raise

    def _release(self, pin):
        try:
            self.gpio.cleanup(pin)
        except Exception:
            logging.getLogger(__name__).exception('GPIO cleanup failed for pin %s', pin)
        finally:
            self.pins.remove(pin)
            self._owners.pop((id(self.gpio), pin), None)

    def close(self):
        with self._lock:
            for pin in self.pins[::-1]:
                self._release(pin)


def stop_process(process):
    """Reap a child on timeout, error or Ctrl+C; do not leave it running."""
    import subprocess
    try:
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    finally:
        for pipe in (process.stdout, process.stderr):
            if pipe is not None:
                pipe.close()


@contextmanager
def sdr_stream(device, direction, sample_format):
    """Close a SoapySDR stream on read/activation errors and cancellation."""
    stream = device.setupStream(direction, sample_format)
    try:
        result = device.activateStream(stream)
        if isinstance(result, int) and result < 0:
            raise RuntimeError(f'SDR stream activation failed: {result}')
        yield stream
    finally:
        try:
            device.deactivateStream(stream)
        except Exception:
            logging.getLogger(__name__).exception('SDR stream deactivation failed')
        try:
            device.closeStream(stream)
        except Exception:
            logging.getLogger(__name__).exception('SDR stream close failed')
