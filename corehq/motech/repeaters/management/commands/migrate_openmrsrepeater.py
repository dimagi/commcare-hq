from corehq.motech.repeaters.utils import RepeaterMigrationHelper
from corehq.motech.openmrs.repeaters import SQLOpenmrsRepeater


class Command(RepeaterMigrationHelper):

    @classmethod
    def couch_doc_type(cls):
        return 'OpenmrsRepeater'

    @classmethod
    def sql_class(cls):
        return SQLOpenmrsRepeater

    @classmethod
    def _get_string_props(cls):
        return ["version", "location_id", "atom_feed_enabled"]

    @classmethod
    def _get_list_props(cls):
        return ['white_listed_case_types', 'black_listed_users']

    @classmethod
    def _get_schema_props(cls):
        return ["openmrs_config", "atom_feed_status"]

    def get_sql_options_obj(self, doc):
        return {
            "options": {
                "include_app_id_param": doc.get("include_app_id_param"),
                "location_id": doc.get("location_id"),
                "openmrs_config": doc.get("openmrs_config"),
                "atom_feed_enabled": doc.get("atom_feed_enabled"),
                "atom_feed_status": doc.get('atom_feed_status'),
                "version": doc.get("version"),
                "white_listed_case_types": doc.get("white_listed_case_types"),
                "black_listed_users": doc.get("black_listed_users")
            }
        }
