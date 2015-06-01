import functools
from django.conf import settings


class RunWithMultipleSettings(object):
    def __init__(self, fn, settings_dicts):
        self.fn = fn
        self.settings_dicts = settings_dicts

    def __call__(self, *args, **kwargs):
        for settings_dict in self.settings_dicts:
            try:
                call_with_settings(self.fn, settings_dict, args, kwargs)
            except Exception:
                print self.fn, 'failed with the following settings:'
                for key, value in settings_dict.items():
                    print 'settings.{} = {!r}'.format(key, value)
                raise


def call_with_settings(fn, settings_dict, args, kwargs):
    keys = settings_dict.keys()
    original_settings = {key: getattr(settings, key, None) for key in keys}
    try:
        # set settings to new values
        for key, value in settings_dict.items():
            setattr(settings, key, value)
        fn(*args, **kwargs)
    finally:
        # set settings back to original values
        for key, value in original_settings.items():
            setattr(settings, key, value)

def run_with_multiple_settings(fn, settings_dicts):
    helper = RunWithMultipleSettings(fn, settings_dicts)

    @functools.wraps(fn)
    def inner(*args, **kwargs):
        return helper(*args, **kwargs)

    return inner

run_pre_and_post_timezone_migration = functools.partial(
    run_with_multiple_settings,
    settings_dicts=[{
        'PHONE_TIMEZONES_SHOULD_BE_PROCESSED': True,
        'PHONE_TIMEZONES_HAVE_BEEN_PROCESSED': True,
    }, {
        'PHONE_TIMEZONES_SHOULD_BE_PROCESSED': False,
        'PHONE_TIMEZONES_HAVE_BEEN_PROCESSED': False,
    }]
)
