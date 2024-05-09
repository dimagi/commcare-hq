import re

from django.conf import settings

from testil import assert_raises

from corehq.apps.domain.models import Domain as CouchModel  # arbitrary couch model
from corehq.apps.users.models import User as Model  # arbitrary SQL model
from corehq.blobs.models import BlobMeta as ShardedModel  # arbitrary SQL model


def test_database_blocker():
    assert not settings.DB_ENABLED

    with assert_raises(AttributeError, msg="Mock object has no attribute 'info'"):
        CouchModel.get_db().info

    with assert_raises(RuntimeError, msg=re.compile("^Database access not allowed")):
        Model.objects.all().explain()

    with assert_raises(RuntimeError, msg=re.compile("^Database access not allowed")):
        ShardedModel.objects.using("p1").all().explain()


def test_unblocked_database_blocker(db):
    assert settings.DB_ENABLED

    assert CouchModel.get_db().info()["db_name"].startswith("test_")

    # these should not raise
    Model.objects.all().explain()
    ShardedModel.objects.using("p1").all().explain()
