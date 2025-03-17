import re

import pytest
from unmagic import use

from django.conf import settings

from corehq.apps.domain.models import Domain as CouchModel  # arbitrary couch model
from corehq.apps.users.models import User as Model  # arbitrary SQL model
from corehq.blobs.models import BlobMeta as ShardedModel  # arbitrary SQL model


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
