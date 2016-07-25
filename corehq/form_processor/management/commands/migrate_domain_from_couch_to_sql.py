from datetime import datetime
from django.core.management.base import LabelCommand, CommandError
from corehq.form_processor.utils import should_use_sql_backend
from corehq.util.dates import iso_string_to_datetime
from couchforms.models import XFormInstance
from fluff.management.commands.ptop_reindexer_fluff import ReindexEventHandler
from pillowtop.reindexer.change_providers.couch import CouchDomainDocTypeChangeProvider


class Command(LabelCommand):

    def handle_label(self, domain, **options):
        if should_use_sql_backend(domain):
            raise CommandError(u'It looks like {} has already been migrated.'.format(domain))

        _do_couch_to_sql_migration(domain)


def _do_couch_to_sql_migration(domain):
    # (optional) collect some information about the domain's cases and forms for cross-checking
    _process_main_forms(domain)
    _copy_unprocessed_forms(domain)
    # (optional) compare the information collected to the information at the beginning


def _process_main_forms(domain):
    last_received_on = datetime.min
    # process main forms (including cases and ledgers)
    for change in _get_main_form_iterator(domain).iter_all_changes():
        form = change.get_document()
        form_received = iso_string_to_datetime(form['received_on'])
        assert last_received_on <= form_received
        last_received_on = form_received
        print 'processing form {}: {}'.format(form['_id'], form_received)
        _migrate_form_and_associated_models(domain, form)


def _get_main_form_iterator(domain):
    return CouchDomainDocTypeChangeProvider(
        couch_db=XFormInstance.get_db(),
        domains=[domain],
        doc_types=['XFormInstance'],
        event_handler=ReindexEventHandler(u'couch to sql migrator ({})'.format(domain)),
    )


def _migrate_form_and_associated_models(domain, form):
    sql_form = _migrate_form_and_attachments(domain, form)
    _migrate_submission_properties(domain, form, sql_form)
    case_stock_result = _process_cases_and_ledgers(domain, sql_form)
    _save_migrated_models(sql_form, case_stock_result)


def _migrate_form_and_attachments(domain, form):
    """
    see form_processor.parsers.form._create_new_xform for what this should do
    """
    # convert couch form to SQL form
    # adjust datetimes (if doing tzmigration)
    # migrate all attachments
    pass


def _migrate_submission_properties(domain, couch_form_json, sql_form):
    """
    See SubmissionPost._set_submission_properties for what this should do
    """
    pass


def _process_cases_and_ledgers(domain, sql_form):
    """
    See SubmissionPost.process_xforms_for_cases for what this should do
    """
    pass


def _save_migrated_models(sql_form, case_stock_result):
    """
    See SubmissionPost.save_processed_models for ~what this should do.
    However, note that that function does some things that this one shouldn't,
    e.g. process ownership cleanliness flags.
    """


def _copy_unprocessed_forms(domain):
    # copy unprocessed forms
    for change in _get_unprocessed_form_iterator(domain).iter_all_changes():
        form = change.get_document()
        print 'copying unprocessed {} {}: {}'.format(form['doc_type'], form['_id'], form['received_on'])
        # save updated models


def _get_unprocessed_form_iterator(domain):
    return CouchDomainDocTypeChangeProvider(
        couch_db=XFormInstance.get_db(),
        domains=[domain],
        doc_types=[
            'XFormArchived',
            'XFormError',
            'XFormDeprecated',
            'XFormDuplicate',
            # todo: need to figure out which of these we plan on supporting
            'XFormInstance-Deleted',
            'HQSubmission',
            'SubmissionErrorLog',
        ],
        event_handler=ReindexEventHandler(u'couch to sql migrator ({} unprocessed forms)'.format(domain)),
    )
