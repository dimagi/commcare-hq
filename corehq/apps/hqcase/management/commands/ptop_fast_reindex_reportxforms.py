from corehq.apps.hqcase.management.commands.ptop_fast_reindexer import ElasticReindexer
from corehq.pillows.reportxform import ReportXFormPillow
from couchforms.models import XFormInstance
from django.conf import settings


class Command(ElasticReindexer):
    help = "Fast reindex of case elastic index by using the case view and reindexing cases"

    doc_class = XFormInstance
    view_name = 'couchforms/all_submissions_by_domain'
    pillow_class = ReportXFormPillow
    file_prefix = "ptop_fast_reindex_Report"

    def full_couch_view_iter(self):
        view_kwargs = self.get_extra_view_kwargs()
        dynamic_domains = getattr(settings, 'ES_XFORM_FULL_INDEX_DOMAINS', [])
        for domain in dynamic_domains:
            rows = self.paginate_view(
                self.db,
                self.view_name,
                startkey=[domain, 'XFormInstance'],
                reduce=False,
                endkey=[domain, 'XFormInstance', {}],
                **view_kwargs
            )
            for row in rows:
                yield row

    def custom_filter(self, view_row):
        """
        Custom filter if you want to do additional filtering based on the view

        Return true if to index, false if to SKIP
        """
        if 'xmlns' in view_row:
            return view_row['xmlns'] != 'http://code.javarosa.org/devicereport'
        elif 'key' in view_row:
            return view_row['key'] != 'http://code.javarosa.org/devicereport'
        else:
            return True
