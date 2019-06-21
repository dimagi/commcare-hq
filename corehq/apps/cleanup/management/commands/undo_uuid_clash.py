from __future__ import absolute_import, print_function

from __future__ import unicode_literals
from collections import defaultdict
from datetime import datetime

import six
from django.core.management.base import BaseCommand

from casexml.apps.case.xform import get_case_updates
from corehq.apps.commtrack.processing import process_stock
from corehq.apps.domain.dbaccessors import iter_domains
from corehq.form_processor.backends.sql.casedb import CaseDbCacheSQL
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL, FormAccessorSQL, LedgerAccessorSQL
from corehq.form_processor.backends.sql.ledger import LedgerProcessorSQL
from corehq.form_processor.backends.sql.processor import FormProcessorSQL
from corehq.form_processor.backends.sql.update_strategy import SqlCaseUpdateStrategy
from corehq.form_processor.models import XFormInstanceSQL, XFormOperationSQL, RebuildWithReason, CaseTransaction, \
    LedgerTransaction
from corehq.sql_db.util import (
    split_list_by_db_partition, new_id_in_same_dbalias, get_db_aliases_for_partitioned_query
)
from dimagi.utils.chunked import chunked
from io import open


def get_forms_to_reprocess(form_ids):
    forms_to_process = []
    edited_forms = {}
    for dbname, forms_by_db in split_list_by_db_partition(form_ids):
        edited_forms.update({
            form.form_id: form for form in
            XFormInstanceSQL.objects.using(dbname)
                .filter(form_id__in=forms_by_db)
                .exclude(deprecated_form_id__isnull=True)
        })

    deprecated_form_ids = {
        form.deprecated_form_id for form in six.itervalues(edited_forms)
    }
    for dbname, forms_by_db in split_list_by_db_partition(deprecated_form_ids):
        deprecated_forms = XFormInstanceSQL.objects.using(dbname).filter(form_id__in=forms_by_db)
        for deprecated_form in deprecated_forms:
            live_form = edited_forms[deprecated_form.orig_id]
            if deprecated_form.xmlns != live_form.xmlns:
                forms_to_process.append((live_form, deprecated_form))

    return forms_to_process


def undo_form_edits(form_tuples, logger):
    cases_to_rebuild = defaultdict(set)
    ledgers_to_rebuild = defaultdict(set)
    operation_date = datetime.utcnow()
    for live_form, deprecated_form in form_tuples:
        # undo corehq.form_processor.parsers.form.apply_deprecation
        case_cache = CaseDbCacheSQL(live_form.domain, load_src="undo_form_edits")
        live_case_updates = get_case_updates(live_form)
        deprecated_case_updates = get_case_updates(deprecated_form)
        case_cache.populate(
            set(cu.id for cu in live_case_updates) | set(cu.id for cu in deprecated_case_updates)
        )

        deprecated_form.form_id = new_id_in_same_dbalias(deprecated_form.form_id)
        deprecated_form.state = XFormInstanceSQL.NORMAL
        deprecated_form.orig_id = None
        deprecated_form.edited_on = None

        live_form.deprecated_form_id = None
        live_form.received_on = live_form.edited_on
        live_form.edited_on = None

        affected_cases, affected_ledgers = update_case_transactions_for_form(
            case_cache, live_case_updates, deprecated_case_updates, live_form, deprecated_form
        )

        for form in (live_form, deprecated_form):
            form.track_create(XFormOperationSQL(
                user_id='system',
                operation=XFormOperationSQL.UUID_DATA_FIX,
                date=operation_date)
            )
            FormAccessorSQL.update_form(form)

        logger.log('Form edit undone: {}, {}({})'.format(
            live_form.form_id, deprecated_form.form_id, deprecated_form.original_form_id
        ))
        cases_to_rebuild[live_form.domain].update(affected_cases)
        ledgers_to_rebuild[live_form.domain].update(affected_ledgers)
        logger.log('Cases to rebuild: {}'.format(','.join(affected_cases)))
        logger.log('Ledgers to rebuild: {}'.format(','.join([l.as_id() for l in affected_ledgers])))

    return cases_to_rebuild, ledgers_to_rebuild


def update_case_transactions_for_form(case_cache, live_case_updates, deprecated_case_updates,
                                      live_form, deprecated_form):
    for case_update in live_case_updates + deprecated_case_updates:
        case_id = case_update.id
        count, _ = CaseTransaction.objects.partitioned_query(case_id)\
            .filter(case_id=case_id, form_id=live_form.form_id).delete()

        rebuild_transactions = CaseTransaction.objects.partitioned_query(case_id).filter(
            case_id=case_id, type=CaseTransaction.TYPE_REBUILD_FORM_EDIT
        )
        for transaction in rebuild_transactions:
            if transaction.details.get('deprecated_form_id') == deprecated_form.original_form_id:
                transaction.delete()

    for case_update in live_case_updates:
        case_id = case_update.id
        case = case_cache.get(case_id)
        SqlCaseUpdateStrategy.add_transaction_for_form(case, case_update, live_form)

    for case_update in deprecated_case_updates:
        case_id = case_update.id
        case = case_cache.get(case_id)
        SqlCaseUpdateStrategy.add_transaction_for_form(case, case_update, deprecated_form)

    stock_result = process_stock([live_form, deprecated_form], case_cache)
    stock_result.populate_models()
    affected_ledgers = set()
    affected_cases = set()
    ledger_transactions = []
    for ledger_value in stock_result.models_to_save:
        affected_ledgers.add(ledger_value.ledger_reference)
        affected_cases.add(ledger_value.case_id)
        for transaction in ledger_value.get_tracked_models_to_create(LedgerTransaction):
            ledger_transactions.append(transaction)

    if affected_cases:
        LedgerAccessorSQL.delete_ledger_transactions_for_form(list(affected_cases), live_form.form_id)

    for transaction in ledger_transactions:
        transaction.save()

    for case in case_cache.cache.values():
        affected_cases.add(case.case_id)
        transactions = case.get_tracked_models_to_create(CaseTransaction)
        for transaction in transactions:
            transaction.case = case
            transaction.save()

    return affected_cases, affected_ledgers


def rebuild_cases(cases_to_rebuild_by_domain, logger):
        detail = RebuildWithReason(reason='undo UUID clash')
        for domain, case_ids in six.iteritems(cases_to_rebuild_by_domain):
            for case_id in case_ids:
                FormProcessorSQL.hard_rebuild_case(domain, case_id, detail)
                logger.log('Case %s rebuilt' % case_id)


def rebuild_ledgers(ledgers_to_rebuild_by_domain, logger):
    for domain, ledger_ids in six.iteritems(ledgers_to_rebuild_by_domain):
        for ledger_id in ledger_ids:
            LedgerProcessorSQL.hard_rebuild_ledgers(domain, **ledger_ids._asdict())
            logger.log('Ledger %s rebuilt' % ledger_id.as_id())


class Command(BaseCommand):
    help = 'Command to reprocess forms that were mistakenly attributed to edit forms due to UUID clash.'

    def add_arguments(self, parser):
        parser.add_argument('--debug', action='store_true', default=False,
                            help='Print forms that need to be reprocessed but not reprocess them')
        parser.add_argument('-d', '--domain')
        parser.add_argument('--db', help='Only process a single Django DB.')
        parser.add_argument('-c', '--case-id', nargs='+', help='Only process cases with these IDs.')

    def handle(self, domain, **options):
        debug = options.get('debug')
        domain = options.get('domain')
        case_ids = options.get('case_id')
        db = options.get('db')

        self.log_filename = 'undo_uuid_clash.{}.log'.format(datetime.utcnow().isoformat())
        print('\nWriting output to log file: {}\n'.format(self.log_filename))

        if case_ids:
            form_ids = set()
            for case in CaseAccessorSQL.get_cases(case_ids):
                assert not domain or case.domain == domain, 'Case "%s" not in domain "%s"' % (case.case_id, domain)
                form_ids.update(case.xform_ids)

            with self:
                check_and_process_forms(form_ids, self, debug)
        else:
            if domain:
                domains = [domain]
            else:
                domains = iter_domains()

            for domain in domains:
                print("Checking domain: %s" % domain)
                form_ids_to_check = set()
                dbs = [db] if db else get_db_aliases_for_partitioned_query()
                for dbname in dbs:
                    form_ids_to_check.update(
                        XFormInstanceSQL.objects.using(dbname)
                        .filter(domain=domain, state=XFormInstanceSQL.DEPRECATED)
                        .values_list('orig_id', flat=True)
                    )

                print('  Found %s forms to check' % len(form_ids_to_check))
                with self:
                    for chunk in chunked(form_ids_to_check, 500):
                        check_and_process_forms(chunk, self, debug)

    def __enter__(self):
        self._log_file = open(self.log_filename, 'w', encoding='utf-8')

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._log_file.close()

    def log(self, message):
        self._log_file.write(message)


def check_and_process_forms(form_ids, logger, debug):
    print('  Checking {} forms'.format(len(form_ids)))
    logger.log('Checking forms: \n{}\n'.format(','.join(form_ids)))
    forms_to_process = get_forms_to_reprocess(form_ids)
    if debug:
        print(forms_to_process)
        return

    print('  Found %s forms to reprocess' % len(forms_to_process) * 2)
    cases_to_rebuild, ledgers_to_rebuild = undo_form_edits(forms_to_process, logger)

    ncases = sum(len(cases) for cases in six.itervalues(cases_to_rebuild))
    print('  Rebuilding %s cases' % ncases)
    rebuild_cases(cases_to_rebuild, logger)

    nledgers = sum(len(ledgers) for ledgers in six.itervalues(ledgers_to_rebuild))
    print('  Rebuilding %s ledgers' % nledgers)
    rebuild_cases(cases_to_rebuild, logger)
