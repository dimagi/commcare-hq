from dimagi.utils.parsing import json_format_datetime

from corehq.apps.cleanup.management.commands.populate_sql_model_from_couch_model import PopulateSQLCommand


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
        return diffs


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
