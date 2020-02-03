from corehq.apps.cleanup.management.commands.populate_sql_model_from_couch_model import PopulateSQLCommand


class Command(PopulateSQLCommand):
    help = """
        Adds a SQLHqDeploy for any HqDeploy doc that doesn't yet have one.
    """

    @property
    def couch_class(self):
        try:
            from corehq.apps.hqadmin.models import HqDeploy
            return HqDeploy
        except ImportError:
            return None

    @property
    def couch_class_key(self):
        return set(['_id'])

    @property
    def sql_class(self):
        from corehq.apps.hqadmin.models import SQLHqDeploy
        return SQLHqDeploy

    def update_or_create_sql_object(self, doc):
        model, created = self.sql_class.objects.get_or_create(
            couch_id=doc['_id'],
            defaults={
                'date': doc['date'],
                'user': doc['user'],
                'environment': doc['environment'],
                'diff_url': doc.get('diff_url'),
            })
        return (model, created)
