from __future__ import absolute_import
import logging
import datetime

from bulk_update.helper import bulk_update as bulk_update_helper
from django.core.management.base import BaseCommand
from django.db.models import Q

from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL
from corehq.form_processor.models import XFormInstanceSQL
from corehq.sql_db.util import split_list_by_db_partition
from dimagi.utils.chunked import chunked


logger = logging.getLogger('set_meta_fields')
logger.setLevel('DEBUG')

META_FIELDS = ("time_end", "time_start", "commcare_version", "app_version")


def sql_iter_forms(form_ids):
    for chunk in chunked(form_ids, 100):
        chunk = chunk(form_ids)
        for form in FormAccessorSQL.get_forms(chunk):
            yield form


def form_ids_by_received_on(from_date, to_date):
    from corehq.sql_db.util import run_query_across_partitioned_databases
    q_expr = Q(received_on__gte=from_date, received_on__lte=to_date)
    needs_update_q = (
        Q(time_end__isnull=True) &
        Q(time_start__isnull=True) &
        Q(commcare_version__isnull=True) &
        Q(app_version__isnull=True)
    )
    q_expr = q_expr & needs_update_q
    return list(run_query_across_partitioned_databases(
        XFormInstanceSQL, q_expr, values=['form_id']
    ))


def set_meta_fields(from_date, to_date, failfast):
    all_form_ids = form_ids_by_received_on(from_date, to_date)
    if not all_form_ids:
        print("No remaining forms to be migrated!")
        return
    total_count = len(all_form_ids)
    updated_count = 0
    skip_count = 0
    # split by partition for bulk updating
    for dbname, form_ids_by_db in split_list_by_db_partition(all_form_ids):
        forms_to_update = []
        for i, form in enumerate(sql_iter_forms(form_ids_by_db)):
            try:
                form.set_meta_properties()
            except Exception as e:
                logger.exception("Error setting meta properties for form {id}".format(id=form.form_id))
                if failfast:
                    raise e
            needs_save = any([getattr(form, field) for field in META_FIELDS])
            if needs_save:
                forms_to_update.append(form)
            else:
                print("Skipping form {} as it doesn't have meta information".format(form.form_id))
                skip_count += 1
            if forms_to_update and i%100==0:
                bulk_update_helper(forms_to_update, using=dbname)
                updated_count += len(forms_to_update)
                forms_to_update = []
        if forms_to_update:
            bulk_update_helper(forms_to_update, using=dbname)
            updated_count += len(forms_to_update)
    print("Updated {updated} forms out of {total} forms, skipped {skipcount}".format(
        updated=updated_count, total=total_count, skipcount=skip_count
    ))


class Command(BaseCommand):
    help = "Set xform meta fields for all XFormInstanceSQL docs"

    def add_arguments(self, parser):
        parser.add_argument(
            '--from_date',
            help='Date after which to update xforms (Inclusive).')
        parser.add_argument(
            '--to_date',
            help='Date before which to update xforms (Inclusive).')
        parser.add_argument(
            '--failfast',
            action='store_true',
            dest='failfast',
            default=False,
            help='Stop processing if there is an error',
        )

    def handle(self, **options):
        if options.get('to_date'):
            to_date = datetime.datetime.strptime(options.get('to_date'), "%d/%m/%y")
        else:
            to_date = datetime.datetime.combine(datetime.datetime.now(), datetime.time.max)
        if options.get('from_date'):
            from_date = datetime.datetime.strptime(options.get('from_date'), "%d/%m/%y")
        else:
            from_date = datetime.datetime.combine(datetime.datetime.now(), datetime.time.min)
        set_meta_fields(from_date, to_date, options.get('failfast'))
