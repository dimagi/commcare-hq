import re
from corehq.form_processor.tests.utils import only_run_with_partitioned_database
from corehq.sql_db.config import partition_config
from django.apps import apps
from django.db import ProgrammingError, transaction
from django.test import TestCase


@only_run_with_partitioned_database
class PartitionedModelsTest(TestCase):

    def assertModelExists(self, model_class, db):
        try:
            with transaction.atomic(using=db):
                # We have to let Django rollback this nested transaction if an Exception
                # is raised otherwise we won't be able to run any more queries.
                model_class.objects.using(db).count()
        except ProgrammingError:
            self.assertTrue(False)

    def assertModelDoesNotExist(self, model_class, db):
        try:
            with transaction.atomic(using=db):
                # We have to let Django rollback this nested transaction if an Exception
                # is raised otherwise we won't be able to run any more queries.
                model_class.objects.using(db).count()
        except ProgrammingError as e:
            self.assertIsNotNone(re.match('.*relation.*does not exist.*', e.message))
        else:
            self.assertTrue(False)

    def get_scheduling_models(self):
        return apps.get_app_config('scheduling').get_models()

    def get_scheduling_partitioned_models(self):
        return apps.get_app_config('scheduling_partitioned').get_models()

    def test_models_are_located_in_correct_dbs(self):
        main_db = partition_config.get_main_db()
        proxy_db = partition_config.get_proxy_db()
        partitioned_dbs = partition_config.get_form_processing_dbs()

        for model_class in self.get_scheduling_models():
            # scheduling models exist in main db
            self.assertModelExists(model_class, main_db)

            # scheduling models do not exist in partitioned dbs
            for db in ([proxy_db] + partitioned_dbs):
                self.assertModelDoesNotExist(model_class, db)

        for model_class in self.get_scheduling_partitioned_models():
            # scheduling partitioned models do not exist in main db
            self.assertModelDoesNotExist(model_class, main_db)

            # scheduling partitioned models exist in paritioned dbs
            for db in ([proxy_db] + partitioned_dbs):
                self.assertModelExists(model_class, db)
