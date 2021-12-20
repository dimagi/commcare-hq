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
        diff_results = []
        list_props = ['white_listed_case_types', 'black_listed_users']
        string_props = ['domain', 'version', 'format']
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
        for prop in list_props:
            for diff in cls.diff_lists(prop, couch.get(prop), getattr(sql, prop)):
                diff_results.append(diff)

        for prop in string_props:
            diff_results.append(cls.diff_value(prop, couch.get(prop), getattr(sql, prop)))

        diff_results = [diff for diff in diff_results if diff]
        return '\n'.join(diff_results) if diff_results else None

    def update_or_create_sql_object(self, doc):
        model, created = self.sql_class().objects.update_or_create(
            repeater_id=doc.get('_id'),
            defaults={
                "domain": doc.get("domain"),
                "connection_settings": ConnectionSettings.objects.get(id=doc.get("connection_settings_id")),
                "is_paused": doc.get("paused"),
                "options": {
                    "format": doc.get("format"),
                    "version": doc.get("version"),
                    "white_listed_case_types": doc.get("white_listed_case_types"),
                    "black_listed_users": doc.get("black_listed_users")
                }
            })
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
