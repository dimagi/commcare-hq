import re
from unittest.mock import call, patch

import pytest
from testil import Config
from unmagic import use

from django.conf import settings

from corehq.apps.domain.models import Domain as CouchModel  # arbitrary couch model
from corehq.apps.users.models import User as Model  # arbitrary SQL model
from corehq.blobs.models import BlobMeta as ShardedModel  # arbitrary SQL model
from corehq.tests.pytest_plugins import reusedb


def test_database_blocker():
    assert not settings.DB_ENABLED

    with pytest.raises(RuntimeError, match=re.compile("^Database access not allowed")):
        CouchModel.get_db().info

    with pytest.raises(RuntimeError, match=re.compile("^Database access not allowed")):
        Model.objects.all().explain()

    with pytest.raises(RuntimeError, match=re.compile("^Database access not allowed")):
        ShardedModel.objects.using("p1").all().explain()


@use("db")
def test_unblocked_database_blocker():
    assert settings.DB_ENABLED

    assert CouchModel.get_db().info()["db_name"].startswith("test_")

    # these should not raise
    Model.objects.all().explain()
    ShardedModel.objects.using("p1").all().explain()


def test_flush_databases_flushes_all_sql_databases():
    sql_databases = [
        (Config(alias='default'), 'test_commcarehq', True),
        (Config(alias='p1'), 'test_commcarehq_p1', True),
    ]
    with (
        patch.object(reusedb, 'get_all_couch_dbs', return_value=[]),
        patch.object(reusedb, 'get_sql_databases', return_value=sql_databases),
        patch.object(reusedb, 'call_command') as call_command,
        patch.object(reusedb, 'bootstrap_migrated_db_state') as bootstrap,
    ):
        reusedb.flush_databases()

    assert call_command.call_args_list == [
        call('flush', interactive=False, database='default'),
        call('flush', interactive=False, database='p1'),
    ]
    bootstrap.assert_called_once_with()


@use("db")
def test_bootstrap_reference_data_restores_seeded_rows():
    from field_audit.models import AuditAction

    from corehq.apps.ota.models import IntegritySamplePercentage
    from corehq.apps.users.models_role import Permission
    from corehq.toggles.sql_models import ToggleEditPermission

    def get_seeded_rows():
        return {
            'permissions': sorted(Permission.objects.values_list('value', flat=True)),
            'sample_percentages': sorted(IntegritySamplePercentage.objects.values_list('percentage', flat=True)),
            'toggle_tags': sorted(ToggleEditPermission.objects.values_list('tag_slug', flat=True)),
        }

    seeded = get_seeded_rows()
    assert all(seeded.values()), seeded
    Permission.objects.all().delete(audit_action=AuditAction.IGNORE)
    IntegritySamplePercentage.objects.all().delete()
    ToggleEditPermission.objects.all().delete()

    reusedb.bootstrap_reference_data()
    assert get_seeded_rows() == seeded

    reusedb.bootstrap_reference_data()  # does not duplicate rows
    assert get_seeded_rows() == seeded
