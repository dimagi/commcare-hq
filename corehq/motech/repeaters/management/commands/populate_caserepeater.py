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
    def couch_doc_type(self):
        return 'CaseRepeater'

    @classmethod
    def sql_class(self):
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
            couch_id=doc['_id'],
            defaults={
                "version": doc.get("version"),
                "repeater_id": doc.get('repeater_id'),
                "domain": doc.get("domain"),
                "connection_settings": doc.get("connection_settings_id"),
                "auth_type": doc.get("auth_type"),
                "notify_addresses_str": doc.get("notify_addresses_str"),
                "format": doc.get("format"),
                "paused": doc.get("paused"),
                "started_at": force_to_datetime(doc.get("started_at")),
                "last_success_at": force_to_datetime(doc.get("last_success_at")),
                "failure_streak": doc.get("failure_streak"),

            })
        # add code to migrate CaseRepeater.white_listed_case_types
        # add code to migrate CaseRepeater.black_listed_users
        return model, created
