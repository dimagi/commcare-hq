import logging
import datetime
from couchforms.dbaccessors import get_form_ids_by_type
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

            form_ids = get_form_ids_by_type(domain, 'XFormInstance',
                                            start=datetime.date(2013, 8, 1),
                                            end=datetime.date(2013, 10, 15))

            for doc in iter_docs(xform_db, form_ids):
                xfrom_doc = XFormInstance.wrap(doc)
                xfrom_doc.update_indicators_in_bulk(indicators, logger=logging)
