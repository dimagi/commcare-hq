from corehq.apps.cleanup.management.commands.populate_sql_model_from_couch_model import PopulateSQLCommand
from corehq.apps.custom_data_fields.models import Field


class Command(PopulateSQLCommand):
    @classmethod
    def couch_db_slug(cls):
        return "meta"

    @classmethod
    def couch_doc_type(self):
        return 'CustomDataFieldsDefinition'

    @classmethod
    def sql_class(self):
        from corehq.apps.custom_data_fields.models import CustomDataFieldsDefinition
        return CustomDataFieldsDefinition

    @classmethod
    def commit_adding_migration(cls):
        return "bb82e5c3d2840d6e3e3a6f5ebf1a0c7e817f4613"

    @classmethod
    def diff_couch_and_sql(cls, doc, obj):
        diffs = []
        for attr in ('field_type', 'domain'):
            diffs.append(cls.diff_attr(attr, doc, obj))
        diffs.extend(cls.diff_lists(doc.get('fields', []), obj.get_fields(), [
            'slug', 'is_required', 'label', 'choices', 'regex', 'regex_msg'
        ]))
        diffs = [d for d in diffs if d]
        return "\n".join(diffs) if diffs else None

    def update_or_create_sql_object(self, doc):
        model, created = self.sql_class().objects.update_or_create(
            couch_id=doc['_id'],
            defaults={
                "domain": doc['domain'],
                "field_type": doc['field_type'],
            },
        )
        model.set_fields([
            Field(
                slug=field['slug'],
                is_required=field.get('is_required', False),
                label=field.get('label', ''),
                choices=field.get('choices', []),
                regex=field.get('regex', ''),
                regex_msg=field.get('regex_msg', ''),
            )
            for field in doc['fields']
        ])
        model.save()
        return (model, created)
