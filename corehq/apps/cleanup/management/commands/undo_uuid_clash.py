from __future__ import absolute_import, print_function

from collections import defaultdict
from datetime import datetime

from django.core.management.base import BaseCommand

from casexml.apps.case.xform import get_case_ids_from_form
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
from corehq.form_processor.backends.sql.processor import FormProcessorSQL
from corehq.form_processor.models import XFormInstanceSQL, XFormOperationSQL, RebuildWithReason
from corehq.sql_db.util import (
    split_list_by_db_partition, new_id_in_same_dbalias, get_db_aliases_for_partitioned_query
)
from dimagi.utils.chunked import chunked


def get_forms_to_reprocess(form_ids):
    forms_to_process = []
    for dbname, forms_by_db in split_list_by_db_partition(form_ids):
        edited_forms = {
            form.form_id: form for form in
            XFormInstanceSQL.objects.using(dbname)
                .filter(form_id__in=forms_by_db)
                .exclude(deprecated_form_id__isnull=True)
        }
        deprecated_forms_ids = {
            form.deprecated_form_id for form in edited_forms.itervalues()
        }
        deprecated_forms = XFormInstanceSQL.objects.using(dbname).filter(form_id__in=deprecated_forms_ids)
        for deprecated_form in deprecated_forms:
            live_form = edited_forms[deprecated_form.orig_id]
            if deprecated_form.xmlns != live_form.xmlns:
                forms_to_process.append(live_form)
                forms_to_process.append(deprecated_form)

    return forms_to_process


def undo_form_edits(forms):
    cases_to_rebuild = defaultdict(set)
    operation_date = datetime.utcnow()
    for form in forms:
        # undo corehq.form_processor.parsers.form.apply_deprecation
        if form.is_deprecated:
            form.form_id = new_id_in_same_dbalias(form.form_id)
            form.state = XFormInstanceSQL.NORMAL
            form.orig_id = None
            form.edited_on = None
            form.date = operation_date
        else:
            form.deprecated_form_id = None
            form.received_on = form.edited_on
            form.edited_on = None

        form.track_create(XFormOperationSQL(
            user_id='system',
            operation=XFormOperationSQL.UUID_DATA_FIX)
        )
        cases_to_rebuild[form.domain].update(get_case_ids_from_form(form))
        form.save()
    return cases_to_rebuild


def rebuild_cases(cases_to_rebuild_by_domain):
        detail = RebuildWithReason(reason='undo UUID clash')
        for domain, case_ids in cases_to_rebuild_by_domain.iteritems():
            for case_id in case_ids:
                FormProcessorSQL.hard_rebuild_case(domain, case_id, detail)


class Command(BaseCommand):
    help = 'Fire all repeaters in a domain.'

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('--db', help='Only process a single Django DB.')
        parser.add_argument('-c', '--case-id', nargs='+', help='Only process cases with these IDs.')

    def handle(self, domain, **options):
        case_ids = options.get('case_id')
        db = options.get('db')

        if case_ids:
            form_ids = set()
            for case in CaseAccessorSQL.get_cases(case_ids):
                assert case.domain == domain, 'Case "%s" not in domain "%s"' % (case.case_id, domain)
                form_ids.update(case.xform_ids)

            check_and_process_forms(form_ids)
        else:
            form_ids_to_check = set()
            dbs = [db] if db else get_db_aliases_for_partitioned_query()
            for dbname in dbs:
                form_ids_to_check.update(
                    XFormInstanceSQL.objects.using(dbname)
                    .filter(domain=domain, state=XFormInstanceSQL.DEPRECATED)
                    .values_list('orig_id', flat=True)
                )

            print('Found %s forms to check' % len(form_ids_to_check))
            for chunk in chunked(form_ids_to_check, 500):
                check_and_process_forms(chunk)


def check_and_process_forms(form_ids):
    print('Checking %s forms' % len(form_ids))
    forms_to_process = get_forms_to_reprocess(form_ids)

    print('Found %s forms to reprocess' % len(forms_to_process))
    cases_to_rebuild = undo_form_edits(forms_to_process)

    ncases = sum(len(cases) for cases in cases_to_rebuild.itervalues())
    print('Rebuilding %s cases' % ncases)
    rebuild_cases(cases_to_rebuild)
