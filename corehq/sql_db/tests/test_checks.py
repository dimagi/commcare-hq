import pytest
from django.test import override_settings
from nose.tools import assert_equal, assert_in

from corehq.sql_db import check_standby_configs

from .utils import ignore_databases_override_warning

DATABASES = {
    'default': {},
    'other': {},
    's1': {
        'HQ_ACCEPTABLE_STANDBY_DELAY': 1
    },
    's2': {
        'STANDBY': {
            'MASTER': 'default'
        }
    },
    's3': {
        'STANDBY': {
            'MASTER': 'other'
        }
    }
}


@pytest.mark.parametrize("config, is_error", [
    ({
        'WRITE': 'default',
        'READ': [
            ('default', 1),
            ('s1', 1),
            ('s2', 1)
        ]
    }, False),
    ({
        'WRITE': 'default',
        'READ': [
            ('default', 1),
            ('s3', 1),
        ]
    }, True),
    ({
        'WRITE': 'default',
        'READ': [
            ('default', 1),
            ('other', 1),
        ]
    }, True),
])
@ignore_databases_override_warning
def test_check_standby_configs(config, is_error):
    settings = {
        'DATABASES': DATABASES,
        'REPORTING_DATABASES': {
            'db_A': config
        }
    }
    with override_settings(**settings):
        errors = check_standby_configs(None)
        if is_error:
            assert_equal(1, len(errors))
            assert_in('settings.REPORTING_DATABASES.db_A', errors[0].msg)
        else:
            assert_equal(0, len(errors))
