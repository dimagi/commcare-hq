from copy import deepcopy

from dateutil import parser

from corehq.apps.es.fake.es_query_fake import HQESQueryFake
from corehq.apps.es.forms import form_adapter


class FormESFake(HQESQueryFake):
    _all_docs = []

    def domain(self, domain):
        return self._filtered(
            lambda doc: (doc.get('domain') == domain
                         or domain in doc.get('domains', [])))

    def xmlns(self, xmlns):
        return self.term('xmlns.exact', xmlns)

    def completed(self, gt=None, gte=None, lt=None, lte=None):
        return self.date_range('form.meta.timeEnd', gt, gte, lt, lte)

    @staticmethod
    def transform_doc(doc):
        doc = deepcopy(doc)
        doc['xmlns.exact'] = doc.get('xmlns', '')
        doc['form.meta.timeEnd'] = parser.parse(doc['form']['meta']['timeEnd'])
        return form_adapter.to_json(doc)

    def count(self):
        return len(self._result_docs)
