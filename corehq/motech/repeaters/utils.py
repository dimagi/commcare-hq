from memoized import memoized

from corehq.apps.cleanup.management.commands.populate_sql_model_from_couch_model import (
    PopulateSQLCommand,
)
from corehq.motech.models import ConnectionSettings
from corehq.motech.repeaters.dbaccessors import (
    get_all_repeater_docs,
    get_repeater_count_for_domains,
    get_repeaters_by_domain,
)


class RepeaterMigrationHelper(PopulateSQLCommand):

    @classmethod
    def commit_adding_migration(cls):
        return "TODO: add once the PR adding this file is merged"

    @classmethod
    def couch_db_slug(cls):
        return "receiverwrapper"

    @classmethod
    def _get_string_props(cls):
        return []

    @classmethod
    def _get_list_props(cls):
        return []

    @classmethod
    def _get_schema_props(cls):
        return []

    @classmethod
    def get_sql_options_obj(cls, doc):
        return {
            "options": {
            }
        }

    @classmethod
    def get_common_attrs_diff(cls, couch, sql):
        diff_results = []
        string_props = ['domain', 'next_attempt_at', 'last_attempt_at']
        diff_results.append(
            cls.diff_value('paused', couch.get('paused'), sql.is_paused)
        )
        diff_results.append(
            cls.diff_value(
                'connection_settings_id',
                couch.get('connection_settings_id'),
                sql.connection_settings.id
            )
        )
        diff_results.append(
            cls.diff_value('repeater_id', couch.get('_id'), sql.repeater_id)
        )

        # Ignore nullish value in format
        if couch.get('format') and sql.format:
            diff_results.append(
                cls.diff_value('format', couch.get('format'), sql.format)
            )

        for prop in string_props:
            diff_results.append(cls.diff_value(prop, couch.get(prop), getattr(sql, prop)))

        return diff_results

    @classmethod
    def get_common_sql_attr_obj(cls, doc):
        format = doc.get("format") if doc.get("format") else None
        return {
            "domain": doc.get("domain"),
            "connection_settings": ConnectionSettings.objects.get(id=doc.get("connection_settings_id")),
            "is_paused": doc.get("paused"),
            "format": format,
        }

    @classmethod
    def diff_couch_and_sql(cls, couch, sql):
        diff_results = cls.get_common_attrs_diff(couch, sql)
        for prop in cls._get_list_props():
            for diff in cls.diff_lists(prop, couch.get(prop), getattr(sql, prop)):
                diff_results.append(diff)

        for prop in cls._get_string_props():
            diff_results.append(cls.diff_value(prop, couch.get(prop), getattr(sql, prop)))

        for prop in cls._get_schema_props():
            if couch.get(prop) != getattr(sql, prop):
                return f"{prop}: couch value != sql value {sql!r}"

        diff_results = [diff for diff in diff_results if diff]
        return diff_results if diff_results else None

    def update_or_create_sql_object(self, doc):
        default_obj = self.get_common_sql_attr_obj(doc)
        options_obj = self.get_sql_options_obj(doc)
        model, created = self.sql_class().objects.update_or_create(
            repeater_id=doc.get('_id'),
            defaults={**default_obj, **options_obj})
        return model, created

    @memoized
    def _get_all_couch_docs_for_model(self):
        return [
            repeater for repeater in get_all_repeater_docs()
            if repeater['doc_type'] == self.couch_doc_type()
        ]

    def _get_couch_doc_count_for_type(self):
        return len(self._get_all_couch_docs_for_model())

    def _get_couch_doc_count_for_domains(self, domains):
        return get_repeater_count_for_domains(domains)

    def _iter_couch_docs_for_domains(self, domains):
        for domain in domains:
            for repeater in get_repeaters_by_domain(domain):
                yield repeater.to_json()
