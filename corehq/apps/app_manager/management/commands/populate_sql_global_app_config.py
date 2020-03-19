from corehq.apps.cleanup.management.commands.populate_sql_model_from_couch_model import PopulateSQLCommand

from corehq.apps.app_manager.models import LATEST_APK_VALUE, LATEST_APP_VALUE


class Command(PopulateSQLCommand):
    @classmethod
    def couch_db_slug(cls):
        return 'apps'

    @classmethod
    def couch_doc_type(cls):
        return 'GlobalAppConfig'

    @classmethod
    def sql_class(cls):
        from corehq.apps.app_manager.models import GlobalAppConfig
        return GlobalAppConfig

    @classmethod
    def commit_adding_migration(cls):
        return "d1ebf3cfbd2a6f4eac8e2aae0b0ca5fe8cc73a94"

    def update_or_create_sql_object(self, doc):
        model, created = self.sql_class().objects.update_or_create(
            domain=doc['domain'],
            app_id=doc['app_id'],
            defaults={
                "apk_prompt": doc['apk_prompt'],
                "app_prompt": doc['app_prompt'],
                "apk_version": doc.get('apk_version', LATEST_APK_VALUE),
                "app_version": doc.get('app_version', LATEST_APP_VALUE),
            })
        return (model, created)
