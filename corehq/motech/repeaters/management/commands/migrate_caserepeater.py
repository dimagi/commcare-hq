from corehq.motech.repeaters.models import SQLCaseRepeater
from corehq.motech.repeaters.utils import RepeaterMigrationHelper


class Command(RepeaterMigrationHelper):

    @classmethod
    def couch_doc_type(cls):
        return 'CaseRepeater'

    @classmethod
    def sql_class(cls):
        return SQLCaseRepeater

    @classmethod
    def _get_string_props(cls):
        return ['version']

    @classmethod
    def _get_list_props(cls):
        return ['white_listed_case_types', 'black_listed_users']

    @classmethod
    def get_sql_options_obj(cls, doc):
        return {
            "options": {
                "version": doc.get("version"),
                "white_listed_case_types": doc.get("white_listed_case_types"),
                "black_listed_users": doc.get("black_listed_users")
            }
        }
