from django.db.models import Count

from dimagi.utils.parsing import json_format_datetime, string_to_utc_datetime

from corehq.apps.cleanup.management.commands.populate_sql_model_from_couch_model import PopulateSQLCommand

from ...models import Repeater, SQLRepeatRecordAttempt, enable_attempts_sync_to_sql


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
        def sql_may_have_next_check():
            if sql.next_check is not None:
                return True
            couch_state = get_state(couch)
            return couch_state == State.Pending or couch_state == State.Fail

        from ...models import State
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
            couch.get("registered_on") or '1970-01-01T00:00:00.000000Z',
            json_format_datetime(sql.registered_at),
        ))
        if sql_may_have_next_check():
            diffs.append(cls.diff_value(
                "next_check",
                couch["next_check"],
                json_format_datetime(sql.next_check) if sql.next_check else sql.next_check,
            ))
        if couch.get("failure_reason") and not couch.get("succeeded"):
            diffs.append(cls.diff_value(
                "failure_reason",
                couch["failure_reason"],
                sql.failure_reason,
            ))

        if "attempts" not in couch:
            if len(sql.attempts) > 1:
                diffs.append(f"attempts: not in couch, {len(sql.attempts)} in sql")
        else:
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

    def _prepare_for_submodel_creation(self, docs):
        query = self.sql_class().objects.filter(
            couch_id__in=[d["_id"] for d in docs if d.get("attempts")],
        ).annotate(
            num_attempts=Count("attempt_set")
        ).order_by().values_list("couch_id", "id", "num_attempts")
        self._sql_id_and_num_attempts_by_couch_id = {c: (s, n) for c, s, n in query}

    def _create_submodels(self, doc, submodel_specs):
        """Create (unsaved) submodels for a previously synced doc

        :returns: Iterable of ``(submodel_type, submodels_list)`` pairs.
        """
        couch_attempts = doc.get("attempts")
        if not couch_attempts:
            return
        sql_id, sql_count = self._sql_id_and_num_attempts_by_couch_id.get(doc["_id"], (None, None))
        if sql_id is not None and sql_count < len(couch_attempts):
            transforms = ATTEMPT_TRANSFORMS
            yield SQLRepeatRecordAttempt, [
                SQLRepeatRecordAttempt(repeat_record_id=sql_id, **{
                    f: trans(attempt) for f, trans in transforms.items()
                })
                for attempt in (couch_attempts[:-sql_count] if sql_count else couch_attempts)
            ]

    def _sql_query_from_docs(self, docs):
        return super()._sql_query_from_docs(docs).prefetch_related("attempt_set")

    @classmethod
    def _get_couch_doc_count_for_type(cls):
        return count_docs()

    @classmethod
    def get_couch_view_name_and_parameters(cls):
        return 'repeaters/repeat_records_by_payload_id', {}

    @classmethod
    def get_couch_view_name_and_parameters_for_domains(cls, domains):
        return 'repeaters/repeat_records_by_payload_id', [{
            'startkey': [domain],
            'endkey': [domain, {}],
        } for domain in domains]

    def should_process(self, result):
        if result['doc'] is None:
            self.logfile.write(f"Ignored null document: {result['id']}\n")
            return False
        return True

    def _get_couch_doc_count_for_domains(self, domains):
        def count_domain_docs(domain):
            return count_docs(startkey=[domain], endkey=[domain, {}])
        return sum(count_domain_docs(d) for d in domains)


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


def get_state(doc):
    from ...models import State
    if doc['succeeded'] and doc.get('cancelled'):
        return State.Empty
    if doc['succeeded']:
        return State.Success
    if doc.get('cancelled'):
        return State.Cancelled
    if doc['failure_reason']:
        return State.Fail
    return State.Pending


ATTEMPT_TRANSFORMS = {
    "state": get_state,
    "message": (lambda doc: (
        doc.get("success_response") if doc.get("succeeded") else doc.get("failure_reason")
    ) or ''),
    "created_at": (lambda doc: string_to_utc_datetime(doc["datetime"])),
}
