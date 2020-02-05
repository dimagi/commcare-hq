from corehq.apps.cleanup.management.commands.populate_sql_model_from_couch_model import PopulateSQLCommand


class Command(PopulateSQLCommand):
    @classmethod
    def couch_doc_type(cls):
        return 'HqDeploy'

    @classmethod
    def couch_key(cls):
        return set(['_id'])

    @classmethod
    def sql_class(cls):
        from corehq.apps.hqadmin.models import SQLHqDeploy
        return SQLHqDeploy

    def update_or_create_sql_object(self, doc):
        model, created = self.sql_class().objects.get_or_create(
            couch_id=doc['_id'],
            defaults={
                'date': doc['date'],
                'user': doc['user'],
                'environment': doc['environment'],
                'diff_url': doc.get('diff_url'),
            })
        return (model, created)
