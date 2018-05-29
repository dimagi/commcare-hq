from __future__ import absolute_import, unicode_literals

from django.utils.translation import ugettext_lazy as _

from corehq.apps.es.case_search import CaseSearchES
from corehq.apps.reports.standard.cases.basic import CaseListReport


class CaseListExplorer(CaseListReport):
    name = _('Case List Explorer')
    slug = 'case_list_explorer'
    search_class = CaseSearchES

