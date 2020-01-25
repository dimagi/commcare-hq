from corehq.apps.cleanup.management.commands.populate_sql_model_from_couch_model import PopulateSQLCommand
from corehq.apps.cloudcare.models import SQLAppGroup


class Command(PopulateSQLCommand):
    @classmethod
    def couch_doc_type(cls):
        return 'ApplicationAccess'

    @classmethod
    def couch_key(cls):
        return set(['domain'])

    @classmethod
    def sql_class(cls):
        from corehq.apps.cloudcare.models import ApplicationAccess
        return ApplicationAccess

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
        return (model, created)
