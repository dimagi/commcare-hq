from __future__ import absolute_import
from __future__ import unicode_literals

from django.core.management import BaseCommand

from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL, FormAccessorSQL


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('domain')

    def handle(self, domain, **options):
        deleted_sql_form_ids = FormAccessorSQL.get_deleted_form_ids_in_domain(domain)
        FormAccessorSQL.hard_delete_forms(domain, deleted_sql_form_ids, delete_attachments=True)

        deleted_sql_case_ids = CaseAccessorSQL.get_deleted_case_ids_in_domain(domain)
        CaseAccessorSQL.hard_delete_cases(domain, deleted_sql_case_ids)
