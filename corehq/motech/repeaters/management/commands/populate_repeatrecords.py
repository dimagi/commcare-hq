from dimagi.utils.parsing import json_format_datetime, string_to_utc_datetime

from corehq.apps.cleanup.management.commands.populate_sql_model_from_couch_model import PopulateSQLCommand
from corehq.util.couch_helpers import paginate_view

from ...models import Repeater, enable_attempts_sync_to_sql


class Command(PopulateSQLCommand):

    @classmethod
    def couch_db_slug(cls):
        return "receiverwrapper"

    @classmethod
    def couch_doc_type(cls):
        return 'RepeatRecord'

    @classmethod
    def sql_class(cls):
        from ...models import SQLRepeatRecord
        return SQLRepeatRecord

    @classmethod
    def commit_adding_migration(cls):
        return "TODO: add once the PR adding this file is merged"

    def handle(self, *args, **kw):
        couch_model_class = self.sql_class()._migration_get_couch_model_class()
        with enable_attempts_sync_to_sql(couch_model_class, True):
            return super().handle(*args, **kw)

    @classmethod
    def diff_couch_and_sql(cls, couch, sql):
        """
        Compare each attribute of the given couch document and sql
        object. Return a list of human-readable strings describing their
        differences, or None if the two are equivalent. The list may
        contain `None` or empty strings.
        """
        fields = ["domain", "payload_id"]
        diffs = [cls.diff_attr(name, couch, sql) for name in fields]
        diffs.append(cls.diff_value(
            "repeater_id",
            couch["repeater_id"],
            sql.repeater_id.hex,
        ))
        diffs.append(cls.diff_value(
            "state",
            get_state(couch),
            sql.state,
        ))
        diffs.append(cls.diff_value(
            "registered_at",
            couch["registered_on"],
            json_format_datetime(sql.registered_at),
        ))
        diffs.append(cls.diff_value(
            "next_check",
            couch["next_check"],
            json_format_datetime(sql.next_check) if sql.next_check else sql.next_check,
        ))
        diffs.append(cls.diff_value(
            "failure_reason",
            couch["failure_reason"] or '',
            sql.failure_reason,
        ))

        def transform(couch_attempts):
            for attempt in couch_attempts:
                yield {f: trans(attempt) for f, trans in transforms.items()}

        transforms = ATTEMPT_TRANSFORMS
        diffs.extend(cls.diff_lists(
            "attempts",
            list(transform(couch["attempts"])),
            sql.attempts,
            transforms,
        ))
        return diffs

    def get_ids_to_ignore(self, docs):
        """Get ids of records that reference missing repeaters

        May include repeaters that have been created since the migration
        started, whose records are already migrated. Also ignore records
        associated with deleted repeaters.

        NOTE: there is a race condition between this repeaters existence
        check and saving new records. A repeater could be deleted
        between when this function is called and when the new records
        are saved, which would cause the migration to fail with
        IntegrityError on "repeater_id" column value. Since that is a
        rare condition, it is not handled. It should be sufficient to
        rerun the migration to recover from that error.
        """
        existing_ids = {id_.hex for id_ in Repeater.objects.filter(
            id__in=list({d["repeater_id"] for d in docs})
        ).values_list("id", flat=True)}
        return {d["_id"] for d in docs if d["repeater_id"] not in existing_ids}

    @classmethod
    def _get_couch_doc_count_for_type(cls):
        return count_docs()

    def _get_all_couch_docs_for_model(self, chunk_size):
        yield from iter_docs(chunk_size)

    def _get_couch_doc_count_for_domains(self, domains):
        def count_domain_docs(domain):
            return count_docs(startkey=[domain], endkey=[domain, {}])
        return sum(count_domain_docs(d) for d in domains)

    def _iter_couch_docs_for_domains(self, domains, chunk_size):
        def iter_domain_docs(domain):
            return iter_docs(chunk_size, startkey=[domain], endkey=[domain, {}])
        for domain in domains:
            yield from iter_domain_docs(domain)


def count_docs(**params):
    from ...models import RepeatRecord
    result = RepeatRecord.get_db().view(
        'repeaters/repeat_records',
        include_docs=False,
        reduce=True,
        **params,
    ).one()
    if not result:
        return 0
    # repeaters/repeat_records's map emits twice per doc, so its count is doubled
    # repeaters/repeat_records_by_payload_id has no reduce, so cannot be used
    assert result['value'] % 2 == 0, result['value']
    return int(result['value'] / 2)


def iter_docs(chunk_size, **params):
    from ...models import RepeatRecord
    # repeaters/repeat_records_by_payload_id's map emits once per document
    for result in paginate_view(
        RepeatRecord.get_db(),
        'repeaters/repeat_records_by_payload_id',
        chunk_size=chunk_size,
        include_docs=True,
        reduce=False,
        **params,
    ):
        yield result['doc']


def get_state(doc):
    from ...models import State
    if doc['succeeded'] and doc['cancelled']:
        return State.Empty
    if doc['succeeded']:
        return State.Success
    if doc['cancelled']:
        return State.Cancelled
    if doc['failure_reason']:
        return State.Fail
    return State.Pending


ATTEMPT_TRANSFORMS = {
    "state": get_state,
    "message": (lambda doc: doc["success_response"] if doc["succeeded"] else doc["failure_reason"]),
    "created_at": (lambda doc: string_to_utc_datetime(doc["datetime"])),
}
