from custom.intrahealth import INTRAHEALTH_DOMAINS
from custom.intrahealth.calculations import update_payment_data_from_form, rebuild_payment_models
from pillowtop.listener import SQLPillowMixIn, PythonPillow
from couchforms.models import XFormInstance
from couchforms.models import doc_types


class IntrahealthPillow(SQLPillowMixIn, PythonPillow):
    document_class = XFormInstance
    document_filter = None
    domains = INTRAHEALTH_DOMAINS
    doc_types = doc_types().keys()

    def python_filter(self, doc):
        assert self.domains
        assert self.doc_type is not None
        return (
            doc.get('domain', object()) in self.domains and
            doc.get('doc_type', object()) in self.doc_types
        )

    def process_sql(self, doc_dict):
        form = XFormInstance.wrap(doc_dict)
        if form.doc_type == 'XFormInstance':
            update_payment_data_from_form(form)
        else:
            # must be an archived or deleted form. have to rebuild
            rebuild_payment_models(form)
