import doctest
from types import SimpleNamespace
from unittest.mock import Mock

from corehq.apps.dump_reload import timing
from corehq.apps.dump_reload.sql.dump import get_objects_to_dump_from_builders
from corehq.apps.dump_reload.timing import DumpTimingLogger


class RecordingLogger:
    """A stand-in logger that renders and stores ``info`` messages."""

    def __init__(self):
        self.messages = []

    def info(self, msg, *args):
        self.messages.append(msg % args if args else msg)


def fake_clock(times):
    """Return a callable yielding successive values from ``times``."""
    it = iter(times)
    return lambda: next(it)


def test_logs_a_batch_line_every_batch_size_objects():
    log = RecordingLogger()
    timer = DumpTimingLogger(
        batch_size=3, logger=log, time_func=fake_clock([0, 10, 20, 30, 40, 50]),
    )
    for _ in range(6):
        timer.tick('app.Model')

    assert log.messages == [
        '[timing] app.Model: 3 objects dumped in 20.00s',
        '[timing] app.Model: 6 objects dumped in 30.00s',
    ]


def test_no_batch_line_before_reaching_batch_size():
    log = RecordingLogger()
    timer = DumpTimingLogger(
        batch_size=10, logger=log, time_func=fake_clock([0, 1, 2]),
    )
    for _ in range(2):
        timer.tick('app.Model')

    assert log.messages == []


def test_finish_logs_summary_with_total_and_average():
    log = RecordingLogger()
    timer = DumpTimingLogger(
        batch_size=10, logger=log, time_func=fake_clock([0, 1, 2, 60]),
    )
    for _ in range(3):
        timer.tick('app.Model')
    timer.finish()

    # total = 60 - 0 = 60s over 3 objects; avg per 10 = 60 / 3 * 10 = 200s
    assert log.messages == [
        '[timing] app.Model: finished 3 objects in 60.00s (avg 200.00s per 10 objects)',
    ]


def test_changing_model_emits_summary_for_previous_model():
    log = RecordingLogger()
    timer = DumpTimingLogger(
        batch_size=10, logger=log, time_func=fake_clock([0, 5, 20, 21, 30]),
    )
    timer.tick('app.First')
    timer.tick('app.First')
    timer.tick('app.Second')  # now=20 -> finalize First (count=2, total=20)
    timer.tick('app.Second')
    timer.finish()  # now=30 -> finalize Second (count=2, started at 20, total=10)

    assert log.messages == [
        '[timing] app.First: finished 2 objects in 20.00s (avg 100.00s per 10 objects)',
        '[timing] app.Second: finished 2 objects in 10.00s (avg 50.00s per 10 objects)',
    ]


def test_finish_with_no_ticks_logs_nothing():
    log = RecordingLogger()
    timer = DumpTimingLogger(batch_size=10, logger=log, time_func=fake_clock([0]))
    timer.finish()

    assert log.messages == []


def test_batch_lines_and_summary_combine_for_a_full_run():
    log = RecordingLogger()
    timer = DumpTimingLogger(
        batch_size=2, logger=log, time_func=fake_clock([0, 10, 20, 30]),
    )
    for _ in range(3):
        timer.tick('app.Model')
    timer.finish()

    # First batch of 2 spans t=0..10; total spans t=0..30 over 3 objects,
    # so avg per 2 = 30 / 3 * 2 = 20s.
    assert log.messages == [
        '[timing] app.Model: 2 objects dumped in 10.00s',
        '[timing] app.Model: finished 3 objects in 30.00s (avg 20.00s per 2 objects)',
    ]


def _model(app_label, name):
    return type(name, (), {'_meta': SimpleNamespace(app_label=app_label)})


class _Builder:
    def __init__(self, *iterators):
        self._iterators = iterators

    def iterators(self):
        return self._iterators


def test_sql_generator_ticks_timer_once_per_object_with_model_label():
    builders = [
        (_model('app', 'First'), _Builder(['a', 'b'], ['c'])),
        (_model('app', 'Second'), _Builder(['d'])),
    ]
    timer = Mock()

    dumped = list(get_objects_to_dump_from_builders(builders, timer=timer))

    assert dumped == ['a', 'b', 'c', 'd']
    assert [c.args for c in timer.tick.call_args_list] == [
        ('app.First',), ('app.First',), ('app.First',), ('app.Second',),
    ]


def test_sql_generator_works_without_a_timer():
    builders = [(_model('app', 'First'), _Builder(['a', 'b']))]

    assert list(get_objects_to_dump_from_builders(builders)) == ['a', 'b']


def test_doctests():
    results = doctest.testmod(timing)
    assert results.failed == 0
