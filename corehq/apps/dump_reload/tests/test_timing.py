import pytest

from corehq.apps.dump_reload.timing import DumpTimingLogger, format_rate


def test_logs_a_batch_line_every_batch_size_rows():
    log = RecordingLogger()
    timer = DumpTimingLogger(batch_size=3, logger=log, time_func=fake_clock([0, 10, 30]))
    timer.start('app.Model')
    for _ in range(6):
        timer.tick()

    assert log.messages == [
        '[timing] app.Model: 3 rows in 10.00s (3 total)',
        '[timing] app.Model: 3 rows in 20.00s (6 total)',
    ]


def test_measure_logs_summary_with_total_and_rate():
    log = RecordingLogger()
    timer = DumpTimingLogger(batch_size=10, logger=log, time_func=fake_clock([0, 0.0108]))
    with timer.measure('app.Model'):
        for _ in range(3):
            timer.tick()

    # 0.0108s / 3 rows -> 1.000 h per 1M rows
    assert log.messages == [
        '[timing] app.Model: finished 3 rows in 0.01s (1.000h /1M rows)',
    ]


def test_logs_one_summary_per_model():
    log = RecordingLogger()
    timer = DumpTimingLogger(
        batch_size=10, logger=log, time_func=fake_clock([0, 0.0072, 0.0072, 0.0216]),
    )
    for label in ['app.First', 'app.Second']:
        with timer.measure(label):
            timer.tick()
            timer.tick()

    # First: 0.0072s/2 -> 1.000h/1M; Second: 0.0144s/2 -> 2.000h/1M
    assert log.messages == [
        '[timing] app.First: finished 2 rows in 0.01s (1.000h /1M rows)',
        '[timing] app.Second: finished 2 rows in 0.01s (2.000h /1M rows)',
    ]


def test_totals_records_total_seconds_per_model():
    timer = DumpTimingLogger(
        batch_size=10, logger=RecordingLogger(), time_func=fake_clock([0, 20, 21, 31]),
    )
    for label in ['app.First', 'app.Second']:
        with timer.measure(label):
            timer.tick()

    assert timer.totals == {'app.First': 20.0, 'app.Second': 10.0}


def test_a_model_with_no_rows_is_silent():
    log = RecordingLogger()
    timer = DumpTimingLogger(batch_size=10, logger=log, time_func=fake_clock([0]))
    with timer.measure('app.Empty'):
        pass

    assert log.messages == []
    assert timer.totals == {}


@pytest.mark.parametrize("total_seconds, row_count, expected", [
    (3600, 1_000_000, '1.000h /1M rows'),       # 1 hour to dump 1M rows
    (3651.84, 1_000_000, '1.014h /1M rows'),    # rounds to 3 decimals
    (7200, 2_000_000, '1.000h /1M rows'),       # scaled by row count
    (0, 1_000_000, '0.000h /1M rows'),          # zero elapsed, positive rows
    (5.0, 0, 'n/a /1M rows'),                   # zero rows: no divide by zero
])
def test_format_rate(total_seconds, row_count, expected):
    assert format_rate(total_seconds, row_count) == expected


class RecordingLogger:
    def __init__(self):
        self.messages = []

    def info(self, msg):
        self.messages.append(msg)


def fake_clock(times):
    it = iter(times)
    return lambda: next(it)
