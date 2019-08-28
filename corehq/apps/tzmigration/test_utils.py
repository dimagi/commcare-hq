import functools

from corehq.util.test_utils import RunConfig, run_with_multiple_configs

run_pre_and_post_timezone_migration = functools.partial(
    run_with_multiple_configs,
    run_configs=[
        RunConfig(
            settings={
                'PHONE_TIMEZONES_SHOULD_BE_PROCESSED': True,
                'PHONE_TIMEZONES_HAVE_BEEN_PROCESSED': True,
            },
        ),
        RunConfig(
            settings={
                'PHONE_TIMEZONES_SHOULD_BE_PROCESSED': False,
                'PHONE_TIMEZONES_HAVE_BEEN_PROCESSED': False,
            },
        )
    ]
)
