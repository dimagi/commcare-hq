from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

from django.core.management.base import BaseCommand

from corehq.apps.es import CaseES
from corehq.apps.hqcase.utils import resave_case
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors

from corehq.util.log import with_progress_bar


class Command(BaseCommand):

    def handle(self, *args, **kwargs):
        case_ids_and_domains = self._get_saved_deleted_case_ids()

        for case_ids_and_domains in with_progress_bar(case_ids_and_domains):
            for case_id, domain in case_ids_and_domains:
                case = CaseAccessors(domain).get_case(case_id)
                resave_case(domain, case)

    @staticmethod
    def _get_saved_deleted_case_ids():
        return CaseES().set_query(
            {
                "term": {
                    "doc_type": "CommCareCase-Deleted"
                }
            }
        ).values_list("_id", "domain")
