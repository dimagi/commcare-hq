from contextlib import contextmanager


@contextmanager
def drop_connected_signals(signal):
    """
    Use as a context manager to temporarily drop signals. Useful in tests.

    with drop_connected_signals(case_post_save):
       case.save()  # signals won't be called
    case.save()  # signals will be called again
    """
    connected_signals = signal.receivers
    signal.receivers = []
    try:
        yield
    finally:
        signal.receivers = connected_signals
