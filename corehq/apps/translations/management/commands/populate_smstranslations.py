from corehq.apps.cleanup.management.commands.populate_sql_model_from_couch_model import PopulateSQLCommand


class Command(PopulateSQLCommand):
    @classmethod
    def couch_doc_type(self):
        return 'StandaloneTranslationDoc'

    @classmethod
    def sql_class(self):
        from corehq.apps.translations.models import SMSTranslations
        return SMSTranslations

    @classmethod
    def commit_adding_migration(cls):
        return "85940ca17ce2f54437c2418fb5146fb0e2ec830a"

    def update_or_create_sql_object(self, doc):
        model, created = self.sql_class().objects.update_or_create(
            couch_id=doc['_id'],
            defaults={
                "domain": doc.get('domain'),
                "langs": doc.get('langs'),
                "translations": doc.get('translations'),
            })
        return (model, created)
