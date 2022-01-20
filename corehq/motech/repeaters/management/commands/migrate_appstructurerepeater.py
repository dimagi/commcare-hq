from corehq.motech.repeaters.models import SQLAppStructureRepeater
from corehq.motech.repeaters.utils import RepeaterMigrationHelper


class Command(RepeaterMigrationHelper):

    @classmethod
    def couch_doc_type(cls):
        return 'AppStructureRepeater'

    @classmethod
    def sql_class(cls):
        return SQLAppStructureRepeater

    @classmethod
    def _get_string_props(cls):
        return ['format']

    @classmethod
    def get_sql_options_obj(cls, doc):
        return {
            "options": {
                "format": doc.get("format")
            }
        }
