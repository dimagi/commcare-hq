from corehq.apps.change_feed import topics
from corehq.apps.change_feed.producer import producer
from corehq.apps.change_feed import data_sources
from pillowtop.feed.interface import ChangeMeta


def publish_form_saved(form):
    producer.send_change(topics.FORM_SQL, _change_meta_from_sql_form(form))


def _change_meta_from_sql_form(form):
    return ChangeMeta(
        document_id=form.form_id,
        data_source_type=data_sources.FORM_SQL,
        data_source_name='form-sql',  # todo: this isn't really needed.
        document_type=form.state,
        document_subtype=form.xmlns,
        domain=form.domain,
        is_deletion=False,
    )


def publish_case_saved(case):
    producer.send_change(topics.CASE_SQL, _change_meta_from_sql_case(case))


def _change_meta_from_sql_case(case):
    return ChangeMeta(
        document_id=case.case_id,
        data_source_type=data_sources.CASE_SQL,
        data_source_name='case-sql',  # todo: this isn't really needed.
        document_type='CommCareCaseSql',  # todo: should this be the same as the couch models?
        document_subtype=case.type,
        domain=case.domain,
        is_deletion=False,
    )
