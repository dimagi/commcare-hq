import functools
from corehq.apps.tzmigration.test_utils import call_with_settings


def NOOP(*args, **kwargs):
    pass


class RunConfig(object):

    def __init__(self, settings, pre_run=None, post_run=None):
        self.settings = settings
        self.pre_run = pre_run or NOOP
        self.post_run = post_run or NOOP


class RunWithMultipleConfigs(object):
    def __init__(self, fn, run_configs):
        self.fn = fn
        self.run_configs = run_configs

    def __call__(self, *args, **kwargs):
        for run_config in self.run_configs:

            def fn_with_pre_and_post(*args, **kwargs):
                # make sure the pre and post run also run with the right settings
                run_config.pre_run(*args, **kwargs)
                self.fn(*args, **kwargs)
                run_config.post_run(*args, **kwargs)

            try:
                call_with_settings(fn_with_pre_and_post, run_config.settings, args, kwargs)
            except Exception:
                print self.fn, 'failed with the following settings:'
                for key, value in run_config.settings.items():
                    print 'settings.{} = {!r}'.format(key, value)
                raise


def run_with_multiple_configs(fn, run_configs):
    helper = RunWithMultipleConfigs(fn, run_configs)

    @functools.wraps(fn)
    def inner(*args, **kwargs):
        return helper(*args, **kwargs)

    return inner


run_with_all_restore_configs = functools.partial(
    run_with_multiple_configs,
    run_configs=[
        # original code
        RunConfig(
            settings={
                'TESTS_SHOULD_USE_CLEAN_RESTORE': False,
                'TESTS_SHOULD_TRACK_CLEANLINESS': False,
            },
            post_run=lambda *args, **kwargs: args[0].tearDown()
        ),
        # clean restore code with cleanliness flags
        RunConfig(
            settings={
                'TESTS_SHOULD_USE_CLEAN_RESTORE': True,
                'TESTS_SHOULD_TRACK_CLEANLINESS': True,
            },
            pre_run=lambda *args, **kwargs: args[0].setUp()
        ),
    ]
)
