from corehq.apps.cleanup.management.commands.populate_sql_model_from_couch_model import (
    PopulateSQLCommand,
)
from corehq.motech.models import ConnectionSettings
from corehq.motech.repeaters.dbaccessors import (
    get_all_repeater_docs,
    get_repeater_count_for_domains,
    get_repeaters_by_domain,
)


class Command(PopulateSQLCommand):
    @classmethod
    def couch_db_slug(cls):
        return "receiverwrapper"

    @classmethod
    def couch_doc_type(cls):
        return 'CaseRepeater'

    @classmethod
    def sql_class(cls):
        from corehq.motech.repeaters.models import SQLCaseRepeater
        return SQLCaseRepeater

    @classmethod
    def commit_adding_migration(cls):
        return "TODO: add once the PR adding this file is merged"

    @classmethod
    def diff_couch_and_sql(cls, couch, sql):
        """
        This should compare each attribute of the given couch document and sql object.
        Return a list of human-reaedable strings describing their differences, or None if the
        two are equivalent. The list may contain `None` or empty strings which will be filtered
        out before display.

        Note: `diff_value`, `diff_attr` and `diff_lists` methods of `PopulateSQLCommand` are useful
        helpers.
        """
        return None

    def update_or_create_sql_object(self, doc):
        model, created = self.sql_class().objects.update_or_create(
            repeater_id=doc.get('_id'),
            defaults={
                "version": doc.get("version"),
                "domain": doc.get("domain"),
                "connection_settings": ConnectionSettings.objects.get(id=doc.get("connection_settings_id")),
                "format": doc.get("format"),
                "is_paused": doc.get("paused"),
                "white_listed_case_types": doc.get("white_listed_case_types"),
                "black_listed_users": doc.get("black_listed_users")
            })
        return model, created
