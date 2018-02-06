import logging
from datetime import datetime

from bulk_update.helper import bulk_update as bulk_update_helper
from django.core.management.base import BaseCommand
from django.db.models import Q

from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.form_processor.models import XFormInstanceSQL
from dimagi.utils.chunked import chunked


logger = logging.getLogger('set_meta_fields')
logger.setLevel('DEBUG')

META_FIELDS = ("time_end", "time_start", "commcare_version", "build_version")


def iter_form_ids_by_domain_received_on(domain, before_date):
    from corehq.sql_db.util import run_query_across_partitioned_databases
    q_expr = Q(domain=domain, received_on__lt=before_date)
    for form_id in run_query_across_partitioned_databases(
            XFormInstanceSQL, q_expr, values=['form_id']):
        yield form_id


def set_meta_fields(domain, before_date, failfast):
    all_form_ids = iter_form_ids_by_domain_received_on(domain, before_date)
    for form_ids in chunked(all_form_ids, 100):
        forms_to_update = []
        for form in FormAccessors(domain).iter_forms(form_ids):
            already_set = any([getattr(form, field) for field in META_FIELDS])
            if not already_set:
                try:
                    form.set_meta_properties()
                except Exception as e:
                    logger.exception("Error setting meta properties for form {id}".format(id=form.form_id))
                    if failfast:
                        raise e
                if any([getattr(form, field) for field in META_FIELDS]):
                    forms_to_update.append(form)
        if forms_to_update:
            print('Updating form_ids: {}'.format(
                ','.join([form.form_id for form in forms_to_update]))
            )
        bulk_update_helper(forms_to_update)


class Command(BaseCommand):
    help = "Set xform meta fields for all XFormInstanceSQL docs"

    def add_arguments(self, parser):
        parser.add_argument('--domain', help='Domain to update xforms in.')
        parser.add_argument(
            '--before_date',
            help='Date before which to update xforms.')
        parser.add_argument(
            '--failfast',
            action='store_true',
            dest='failfast',
            default=False,
            help='Stop processing if there is an error',
        )

    def handle(self, **options):
        domain = options.get('domain')
        if options.get('before_date'):
            before_date = datetime.strptime(options.get('before_date'), "%d/%m/%y")
        else:
            before_date = datetime.today()
        set_meta_fields(domain, before_date, options.get('failfast'))
