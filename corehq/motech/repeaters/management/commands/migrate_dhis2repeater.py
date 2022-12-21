from corehq.motech.repeaters.utils import RepeaterMigrationHelper
from corehq.motech.dhis2.repeaters import SQLDhis2Repeater


class Command(RepeaterMigrationHelper):

    @classmethod
    def couch_doc_type(cls):
        return 'Dhis2Repeater'

    @classmethod
    def sql_class(cls):
        return SQLDhis2Repeater

    @classmethod
    def _get_schema_props(cls):
        return ['dhis2_config']

    def get_sql_options_obj(self, doc):
        return {
            "options": {
                "include_app_id_param": doc.get("include_app_id_param"),
                "dhis2_config": doc.get("dhis2_config"),
                "white_listed_form_xmlns": doc.get("white_listed_form_xmlns")

            }
        }
