"""Bounded capture in a disposable subprocess (Windows spawn compatible).

No input injection. A hung screenshot cannot block the main scheduler forever.
"""
import multiprocessing as mp
from io import BytesIO


def _worker(bounds, conn):
    try:
        from PIL import ImageGrab
        x, y, w, h = bounds
        image = ImageGrab.grab(bbox=(x, y, x + w, y + h), all_screens=True)
        output = BytesIO()
        image.save(output, format='PNG')
        conn.send_bytes(output.getvalue())
    except BaseException:
        pass
    finally:
        conn.close()


class CaptureWatchdog:
    def __init__(self, timeout=3.0, max_bytes=20_000_000, context=None):
        if timeout <= 0 or max_bytes <= 0:
            raise ValueError('positive timeout and max_bytes required')
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.ctx = context or mp.get_context('spawn')

    def capture(self, rect):
        parent, child = self.ctx.Pipe(duplex=False)
        process = self.ctx.Process(target=_worker, args=((rect.x, rect.y, rect.width, rect.height), child))
        process.daemon = True
        try:
            process.start()
            child.close()
            if not parent.poll(self.timeout):
                return None
            size = parent.recv_bytes(self.max_bytes)
            return size if size.startswith(b'\x89PNG\r\n\x1a\n') else None
        except (EOFError, OSError, ValueError):
            return None
        finally:
            parent.close()
            if process.pid is not None:
                if process.is_alive():
                    process.terminate()
                process.join(timeout=1)
                if process.is_alive():
                    process.kill()
                    process.join(timeout=1)
            else:
                child.close()
