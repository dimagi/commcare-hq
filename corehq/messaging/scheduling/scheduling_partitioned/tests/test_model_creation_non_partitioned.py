import re
from corehq.form_processor.tests.utils import only_run_with_non_partitioned_database
from django.apps import apps
from django.db import ProgrammingError, transaction
from django.test import TestCase


@only_run_with_non_partitioned_database
class NonPartitionedModelsTest(TestCase):

    def assertModelExists(self, model_class, db):
        try:
            with transaction.atomic(using=db):
                # We have to let Django rollback this nested transaction if an Exception
                # is raised otherwise we won't be able to run any more queries.
                model_class.objects.using(db).count()
        except ProgrammingError:
            self.assertTrue(False)

    def get_scheduling_models(self):
        return apps.get_app_config('scheduling').get_models()

    def get_scheduling_partitioned_models(self):
        return apps.get_app_config('scheduling_partitioned').get_models()

    def test_models_are_located_in_correct_db(self):
        main_db = 'default'

        for model_class in self.get_scheduling_models():
            self.assertModelExists(model_class, main_db)

        for model_class in self.get_scheduling_partitioned_models():
            self.assertModelExists(model_class, main_db)
