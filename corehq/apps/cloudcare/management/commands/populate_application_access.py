from corehq.apps.cleanup.management.commands.populate_sql_model_from_couch_model import PopulateSQLCommand
from corehq.apps.cloudcare.models import SQLAppGroup


class Command(PopulateSQLCommand):
    @classmethod
    def couch_doc_type(cls):
        return 'ApplicationAccess'

    @classmethod
    def sql_class(cls):
        from corehq.apps.cloudcare.models import ApplicationAccess
        return ApplicationAccess

    @classmethod
    def commit_adding_migration(cls):
        return "1e099ff2f11cc6c3c7a0d647f1a67f32994ac01b"

    def update_or_create_sql_object(self, doc):
        model, created = self.sql_class().objects.update_or_create(
            domain=doc['domain'],
            defaults={
                "restrict": doc['restrict'],
            },
        )
        model.sqlappgroup_set.all().delete()
        model.sqlappgroup_set.set([
            SQLAppGroup(app_id=group['app_id'], group_id=group['group_id'])
            for group in doc['app_groups']
        ], bulk=False)
        model.save()
        return (model, created)
