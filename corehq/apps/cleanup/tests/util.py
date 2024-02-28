import inspect
from datetime import datetime

from django.db import models
from django.test import SimpleTestCase

from dimagi.ext.couchdbkit import Document
from dimagi.utils.couch.migration import (
    SyncCouchToSQLMixin,
    SyncSQLToCouchMixin,
)

from corehq.apps.cleanup.models import DeletedSQLDoc
from corehq.util.test_utils import unit_testing_only


class ModelAttrEqualityHelper(SimpleTestCase):
    """
    Helper class to test the equality of couch and a SQL models during a couch to sql migration.
    Update `couch_only_attrs` and `sql_only_attrs` as per requirements
    """
    class DummySQLModel(models.Model, SyncSQLToCouchMixin):
        pass

    class DummyCouchModel(Document, SyncCouchToSQLMixin):
        pass

    couch_only_attrs = set()

    sql_only_attrs = set()

    @classmethod
    def _get_user_defined_attrs(cls, model_cls, dummy_model):
        model_attrs = dir(dummy_model)
        return {item[0]
                for item in inspect.getmembers(model_cls)
                if item[0] not in model_attrs}

    @classmethod
    def get_sql_attrs(cls, model_cls):
        return cls._get_user_defined_attrs(model_cls, cls.DummySQLModel)

    @classmethod
    def get_cleaned_couch_attrs(cls, couch_model_cls):
        couch_attrs = cls._get_user_defined_attrs(couch_model_cls, cls.DummyCouchModel)
        extra_attrs = cls.couch_only_attrs
        new_attrs = cls.sql_only_attrs
        return (couch_attrs - extra_attrs).union(new_attrs)


def is_monday():
    return datetime.utcnow().isoweekday() == 1


@unit_testing_only
def delete_all_deleted_sql_docs():
    DeletedSQLDoc.objects.all().delete()
