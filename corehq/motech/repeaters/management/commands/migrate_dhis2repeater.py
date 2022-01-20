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
    def _get_string_props(cls):
        return ['format']

    def get_sql_options_obj(self, doc):
        return {
            "options": {
                "include_app_id_param": doc.get("include_app_id_param"),
                "dhis2_config": doc.get("dhis2_config"),
                "format": doc.get("format"),
                "white_listed_form_xmlns": doc.get("white_listed_form_xmlns")

            }
        }

    @classmethod
    def diff_couch_and_sql(cls, couch, sql):
        diff_results = cls.get_common_attrs_diff(couch, sql)
        # Todo finish it
        for prop in cls._get_string_props():
            diff_results.append(cls.diff_value(prop, couch.get(prop), getattr(sql, prop)))

        diff_results = [diff for diff in diff_results if diff]
        return '\n'.join(diff_results) if diff_results else None
