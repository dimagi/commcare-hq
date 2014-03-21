import logging
from dimagi.utils.couch.database import iter_docs
from corehq.apps.indicators.utils import get_namespaces, get_indicator_domains
from django.core.management.base import LabelCommand
from corehq.apps.indicators.models import FormIndicatorDefinition
from couchforms.models import XFormInstance


class Command(LabelCommand):
    help = "Update MVP form indicators that may have been missed due to processing from Aug-Sep."

    def handle(self, *args, **options):
        xform_db = XFormInstance.get_db()

        for domain in get_indicator_domains():
            namespaces = get_namespaces(domain)
            indicators = []
            for namespace in namespaces:
                indicators.extend(FormIndicatorDefinition.get_all(namespace, domain))

            key = [domain, "by_type", "XFormInstance"]
            data = xform_db.view(
                'couchforms/all_submissions_by_domain',
                startkey=key+["2013-08-01"],
                endkey=key+["2013-10-15"],
                reduce=False,
                include_docs=False
            ).all()
            form_ids = [d['id'] for d in data]

            for doc in iter_docs(xform_db, form_ids):
                xfrom_doc = XFormInstance.wrap(doc)
                xfrom_doc.update_indicators_in_bulk(indicators, logger=logging)
