import logging
import time
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class DumpTimingLogger:
    """Logs per-model export timing during a domain dump. Wrap each model in
    :meth:`measure` and call :meth:`tick` per row; a model with no rows is silent.
    """

    def __init__(self, batch_size=10000, logger=logger, time_func=time.monotonic):
        self.batch_size = batch_size
        self.logger = logger
        self.time_func = time_func
        self.totals = {}  # seconds per model
        self._label = None
        self._model_start = None
        self._batch_start = None
        self._count = 0

    @contextmanager
    def measure(self, model_label):
        self.start(model_label)
        try:
            yield
        finally:
            self.stop()

    def start(self, model_label):
        now = self.time_func()
        self._label = model_label
        self._model_start = now
        self._batch_start = now
        self._count = 0

    def tick(self):
        self._count += 1
        if self._count % self.batch_size == 0:
            now = self.time_func()
            self.logger.info(
                f"[timing] {self._label}: {self.batch_size} rows in "
                f"{now - self._batch_start:.2f}s ({self._count} total)"
            )
            self._batch_start = now

    def stop(self):
        if self._count:
            total = self.time_func() - self._model_start
            self.totals[self._label] = self.totals.get(self._label, 0) + total
            self.logger.info(
                f"[timing] {self._label}: finished {self._count} rows in "
                f"{total:.2f}s ({format_rate(total, self._count)})"
            )
        self._label = None


def format_rate(total_seconds, row_count):
    """Throughput as hours per million rows, e.g. ``1.014h /1M rows`` (``n/a`` for zero rows)."""
    if not row_count:
        return 'n/a /1M rows'
    hours_per_million = total_seconds / row_count * 1_000_000 / 3600
    return f'{hours_per_million:.3f}h /1M rows'
