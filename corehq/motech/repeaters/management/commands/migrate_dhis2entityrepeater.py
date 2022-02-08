from corehq.motech.repeaters.utils import RepeaterMigrationHelper
from corehq.motech.dhis2.repeaters import SQLDhis2EntityRepeater


class Command(RepeaterMigrationHelper):

    @classmethod
    def couch_doc_type(cls):
        return 'Dhis2EntityRepeater'

    @classmethod
    def sql_class(cls):
        return SQLDhis2EntityRepeater

    @classmethod
    def _get_string_props(cls):
        return ["version", "include_app_id_param"]

    @classmethod
    def _get_list_props(cls):
        return ['white_listed_case_types', 'black_listed_users']

    @classmethod
    def _get_schema_props(cls):
        return ['dhis2_entity_config']

    def get_sql_options_obj(self, doc):
        return {
            "options": {
                "include_app_id_param": doc.get("include_app_id_param"),
                "dhis2_entity_config": doc.get("dhis2_entity_config"),
                "version": doc.get("version"),
                "white_listed_case_types": doc.get("white_listed_case_types"),
                "black_listed_users": doc.get("black_listed_users")
            }
        }
