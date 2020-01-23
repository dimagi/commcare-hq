from corehq.apps.cleanup.management.commands.populate_sql_model_from_couch_model import PopulateSQLCommand
from corehq.apps.cloudcare.models import SQLAppGroup


class Command(PopulateSQLCommand):
    help = """
        Adds a SQLApplicationAccess for any ApplicationAccess doc that doesn't yet have one.
    """

    @property
    def couch_doc_type(self):
        return 'ApplicationAccess'

    @property
    def couch_key(self):
        return set(['domain'])

    @property
    def sql_class(self):
        from corehq.apps.cloudcare.models import SQLApplicationAccess
        return SQLApplicationAccess

    def update_or_create_sql_object(self, doc):
        model, created = self.sql_class.objects.update_or_create(
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
