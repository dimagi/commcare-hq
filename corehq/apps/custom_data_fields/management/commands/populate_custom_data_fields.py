from corehq.apps.cleanup.management.commands.populate_sql_model_from_couch_model import PopulateSQLCommand
from corehq.apps.custom_data_fields.models import SQLField


class Command(PopulateSQLCommand):
    @classmethod
    def couch_db_slug(cls):
        return "meta"

    @classmethod
    def couch_doc_type(self):
        return 'CustomDataFieldsDefinition'

    @classmethod
    def sql_class(self):
        from corehq.apps.custom_data_fields.models import SQLCustomDataFieldsDefinition
        return SQLCustomDataFieldsDefinition

    @classmethod
    def commit_adding_migration(cls):
        return "ff0443ec554edf75015f03842441fc8553cf6d88"

    def update_or_create_sql_object(self, doc):
        model, created = self.sql_class().objects.update_or_create(
            couch_id=doc['_id'],
            defaults={
                "domain": doc['domain'],
                "field_type": doc['field_type'],
            },
        )
        model.set_fields([
            SQLField(
                slug=field['slug'],
                is_required=field.get('is_required', False),
                label=field.get('label', ''),
                choices=field.get('choices', []),
                regex=field.get('regex', ''),
                regex_msg=field.get('regex_msg', ''),
            )
            for field in doc['fields']
        ])
        model.save(sync_to_couch=False)
        return (model, created)
