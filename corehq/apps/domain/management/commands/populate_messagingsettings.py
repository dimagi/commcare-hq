from corehq.apps.cleanup.management.commands.populate_sql_model_from_couch_model import PopulateSQLCommand

from corehq.apps.domain.models import MessagingSettings


class Command(PopulateSQLCommand):
    @classmethod
    def couch_db_slug(cls):
        return "domains"

    @classmethod
    def couch_doc_type(cls):
        return 'Domain'

    @classmethod
    def sql_class(cls):
        return MessagingSettings

    def get_sql_obj(self, doc):
        return self.sql_class().objects.get_or_create(domain=doc['name'])[0]

    @classmethod
    def commit_adding_migration(cls):
        return "TODO"

    @classmethod
    def diff_couch_and_sql(cls, couch, sql):
        couch_value = couch.get('granted_messaging_access', True)
        sql_value = sql.granted_access
        diff = cls.diff_value('granted_access', couch_value, sql_value)
        return [diff] if diff else None

    def update_or_create_sql_object(self, doc):
        print(f"{doc['name']} => {doc.get('granted_messaging_access')}")
        return self.sql_class().objects.update_or_create(domain=doc['name'], defaults={
            'granted_access': doc.get('granted_messaging_access', True),
        })
