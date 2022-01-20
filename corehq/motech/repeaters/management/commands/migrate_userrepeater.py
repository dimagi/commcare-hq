from corehq.motech.repeaters.models import SQLUserRepeater
from corehq.motech.repeaters.utils import RepeaterMigrationHelper


class Command(RepeaterMigrationHelper):

    @classmethod
    def couch_doc_type(cls):
        return 'UserRepeater'

    @classmethod
    def sql_class(cls):
        return SQLUserRepeater

    @classmethod
    def _get_string_props(cls):
        return ['format']

    @classmethod
    def get_sql_options_obj(self, doc):
        return {
            "options": {
                "format": doc.get("format")
            }
        }
