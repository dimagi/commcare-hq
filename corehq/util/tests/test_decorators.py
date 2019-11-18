from testil import eq

from corehq.util.decorators import run_only_when


def test_run_only_when_true():
    should_run_ran = False

    @run_only_when(True)
    def should_run():
        nonlocal should_run_ran
        should_run_ran = True
        return 'ran'

    eq(should_run(), 'ran')
    eq(should_run_ran, True)


def test_run_only_when_false():
    should_not_run_ran = False

    @run_only_when(False)
    def should_not_run():
        nonlocal should_not_run_ran
        should_not_run_ran = True
        return 'ran'

    eq(should_not_run(), None)
    eq(should_not_run_ran, False)
