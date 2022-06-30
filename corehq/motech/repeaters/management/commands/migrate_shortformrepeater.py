from corehq.motech.repeaters.models import SQLShortFormRepeater
from corehq.motech.repeaters.utils import RepeaterMigrationHelper


class Command(RepeaterMigrationHelper):

    @classmethod
    def couch_doc_type(cls):
        return 'ShortFormRepeater'

    @classmethod
    def sql_class(cls):
        return SQLShortFormRepeater

    @classmethod
    def _get_string_props(cls):
        return ['version']

    def get_sql_options_obj(self, doc):
        return {
            "options": {
                "version": doc.get("version")
            }
        }
