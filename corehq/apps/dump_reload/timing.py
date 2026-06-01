"""Per-model timing instrumentation for domain data dumps.

Enabled by the ``--timing`` flag on the ``dump_domain_data`` command, this
records the wall-clock time taken to export each model: a line for every
``batch_size`` objects, and a summary (total time and average time per
``batch_size`` objects) when a model finishes.

Timing is approximate. Objects are produced and serialized lazily through a
generator, so the interval measured for a batch may include the production or
serialization of one object from an adjacent batch. This is negligible over
large batches and adequate for diagnosing which models are slow to dump.
"""
import logging
import time

logger = logging.getLogger(__name__)


class DumpTimingLogger:
    """Accumulates and logs per-model export timing.

    Call :meth:`tick` once per object as it is dumped, passing the model
    label. Objects for a given model are expected to arrive consecutively; the
    summary for a model is emitted when the first object of the next model
    arrives, or when :meth:`finish` is called at the end of the dump.

    >>> log = logging.getLogger('doctest')
    >>> clock = iter([0, 1, 2]).__next__
    >>> timer = DumpTimingLogger(batch_size=2, logger=log, time_func=clock)
    >>> timer.tick('app.Model')
    >>> timer.tick('app.Model')  # second object completes a batch of 2
    >>> timer.finish()
    """

    def __init__(self, batch_size=10000, logger=logger, time_func=time.monotonic):
        self.batch_size = batch_size
        self.logger = logger
        self.time_func = time_func
        self._current_label = None
        self._model_start = None
        self._batch_start = None
        self._count = 0

    def tick(self, model_label):
        now = self.time_func()
        if model_label != self._current_label:
            self._finish_current(now)
            self._current_label = model_label
            self._model_start = now
            self._batch_start = now
            self._count = 0
        self._count += 1
        if self._count % self.batch_size == 0:
            self.logger.info(
                "[timing] %s: %s objects dumped in %.2fs",
                model_label, self._count, now - self._batch_start,
            )
            self._batch_start = now

    def finish(self):
        """Emit the summary for the model currently being timed, if any."""
        self._finish_current(self.time_func())

    def _finish_current(self, now):
        if self._current_label is None or not self._count:
            return
        total = now - self._model_start
        avg = total / self._count * self.batch_size
        self.logger.info(
            "[timing] %s: finished %s objects in %.2fs (avg %.2fs per %s objects)",
            self._current_label, self._count, total, avg, self.batch_size,
        )
        self._current_label = None
        self._count = 0
