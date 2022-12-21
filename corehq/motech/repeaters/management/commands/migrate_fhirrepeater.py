from corehq.motech.repeaters.utils import RepeaterMigrationHelper
from corehq.motech.fhir.repeaters import SQLFHIRRepeater


class Command(RepeaterMigrationHelper):

    @classmethod
    def couch_doc_type(cls):
        return 'FHIRRepeater'

    @classmethod
    def sql_class(cls):
        return SQLFHIRRepeater

    @classmethod
    def _get_string_props(cls):
        return [
            "version", "include_app_id_param",
            "fhir_version", "patient_registration_enabled", "patient_search_enabled"
        ]

    @classmethod
    def _get_list_props(cls):
        return ['white_listed_case_types', 'black_listed_users']

    def get_sql_options_obj(self, doc):
        return {
            "options": {
                "version": doc.get("version"),
                "white_listed_case_types": doc.get("white_listed_case_types"),
                "black_listed_users": doc.get("black_listed_users"),
                "include_app_id_param": doc.get("include_app_id_param"),
                "fhir_version": doc.get("fhir_version"),
                "patient_registration_enabled": doc.get("patient_registration_enabled"),
                "patient_search_enabled": doc.get("patient_search_enabled"),
            }
        }
