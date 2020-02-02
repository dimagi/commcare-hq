from corehq.apps.cleanup.management.commands.populate_sql_model_from_couch_model import PopulateSQLCommand

from custom.openclinica.models import SQLStudySettings

class Command(PopulateSQLCommand):
    @classmethod
    def couch_doc_type(cls):
        return 'OpenClinicaSettings'

    @classmethod
    def couch_key(cls):
        return set(['domain'])

    @classmethod
    def sql_class(cls):
        from custom.openclinica.models import SQLOpenClinicaSettings
        return SQLOpenClinicaSettings

    def update_or_create_sql_object(self, doc):
        study = doc.get('study', {})
        model, created = self.sql_class().objects.get_or_create(domain=doc['domain'])
        model.sqlstudysettings, created_settings = SQLStudySettings.objects.update_or_create(
            open_clinica_settings=model,
            is_ws_enabled=study.get('is_ws_enabled', False),
            url=study.get('url'),
            username=study.get('username'),
            password=study.get('password'),
            protocol_id=study.get('protocol_id'),
            metadata=study.get('metadata'),
        )
        return (model, created)
