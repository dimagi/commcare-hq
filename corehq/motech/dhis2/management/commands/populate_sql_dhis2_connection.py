from corehq.apps.cleanup.management.commands.populate_sql_model_from_couch_model import PopulateSQLCommand


class Command(PopulateSQLCommand):
    @classmethod
    def couch_doc_type(cls):
        return 'Dhis2Connection'

    @classmethod
    def sql_class(cls):
        from corehq.motech.dhis2.models import Dhis2Connection
        return Dhis2Connection

    @classmethod
    def commit_adding_migration(cls):
        return "d670f19bfda1ab4e842d7d47162c5691b9bef55d"

    def update_or_create_sql_object(self, doc):
        model, created = self.sql_class().objects.update_or_create(
            domain=doc['domain'],
            defaults={
                'server_url': doc.get('server_url'),
                'username': doc.get('username'),
                'password': doc.get('password'),
                'skip_cert_verify': doc.get('skip_cert_verify') or False,
            }
        )
        return (model, created)
