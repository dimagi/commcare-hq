from corehq.motech.repeaters.models import SQLFormRepeater
from corehq.motech.repeaters.utils import RepeaterMigrationHelper


class Command(RepeaterMigrationHelper):

    @classmethod
    def couch_doc_type(cls):
        return 'FormRepeater'

    @classmethod
    def sql_class(cls):
        return SQLFormRepeater

    @classmethod
    def _get_string_props(cls):
        return ['include_app_id_param']

    @classmethod
    def _get_list_props(cls):
        return ['white_listed_form_xmlns', 'user_blocklist']

    @classmethod
    def get_sql_options_obj(cls, doc):
        return {
            "options": {
                "white_listed_form_xmlns": doc.get("white_listed_form_xmlns"),
                "include_app_id_param": doc.get("include_app_id_param"),
                "user_blocklist": doc.get("user_blocklist")
            }
        }
