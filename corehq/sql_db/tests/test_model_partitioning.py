import re

from corehq.form_processor.tests.utils import (
    only_run_with_partitioned_database,
    only_run_with_non_partitioned_database,
)
from corehq.sql_db.config import partition_config
from django.apps import apps
from django.db import ProgrammingError, transaction, DEFAULT_DB_ALIAS
from django.test import TestCase

from corehq.util.test_utils import generate_cases


class PartitionedModelsTestMixin(object):

    def assertModelExists(self, model_class, db):
        try:
            with transaction.atomic(using=db):
                # We have to let Django rollback this nested transaction if an Exception
                # is raised otherwise we won't be able to run any more queries.
                model_class.objects.using(db).count()
        except ProgrammingError:
            self.fail()

    def assertModelDoesNotExist(self, model_class, db):
        try:
            with transaction.atomic(using=db):
                # We have to let Django rollback this nested transaction if an Exception
                # is raised otherwise we won't be able to run any more queries.
                model_class.objects.using(db).count()
        except ProgrammingError as e:
            self.assertIsNotNone(re.match('.*relation.*does not exist.*', str(e)))
        else:
            self.fail()

    def get_models(self, app_label):
        return apps.get_app_config(app_label).get_models()


@only_run_with_partitioned_database
class TestPartitionedModelsWithMultipleDBs(PartitionedModelsTestMixin, TestCase):
    pass


@generate_cases([
    ('scheduling', False),
    ('scheduling_partitioned', True),
    ('form_processor', True),
], TestPartitionedModelsWithMultipleDBs)
def test_models_are_located_in_correct_dbs(self, app_label, is_partitioned):
    proxy_db = partition_config.proxy_db
    partitioned_dbs = partition_config.form_processing_dbs

    for model_class in self.get_models(app_label):
        if is_partitioned:
            # models do not exist in main db
            self.assertModelDoesNotExist(model_class, DEFAULT_DB_ALIAS)

            # models exist in paritioned dbs
            for db in ([proxy_db] + partitioned_dbs):
                self.assertModelExists(model_class, db)
        else:
            # models exist in main db
            self.assertModelExists(model_class, DEFAULT_DB_ALIAS)

            # models do not exist in partitioned dbs
            for db in ([proxy_db] + partitioned_dbs):
                self.assertModelDoesNotExist(model_class, db)


@only_run_with_non_partitioned_database
class TestPartitionedModelsWithSingleDB(PartitionedModelsTestMixin, TestCase):
    pass


@generate_cases([
    ('scheduling',),
    ('scheduling_partitioned',),
    ('form_processor',),
], TestPartitionedModelsWithSingleDB)
def test_models_are_located_in_correct_db(self, app_label):
    main_db = DEFAULT_DB_ALIAS

    for model_class in self.get_models(app_label):
        self.assertModelExists(model_class, main_db)
