from corehq.motech.repeaters.models import SQLLocationRepeater
from corehq.motech.repeaters.utils import RepeaterMigrationHelper


class Command(RepeaterMigrationHelper):

    @classmethod
    def couch_doc_type(cls):
        return 'LocationRepeater'

    @classmethod
    def sql_class(cls):
        return SQLLocationRepeater

    @classmethod
    def _get_string_props(cls):
        return ['format']

    def get_sql_options_obj(self, doc):
        return {
            "options": {
                "format": doc.get("format")
            }
        }
