from corehq.apps.es.fake.es_query_fake import HQESQueryFake


class GroupESFake(HQESQueryFake):
    _all_docs = []

    def is_case_sharing(self, value=True):
        return self._filtered(lambda doc: doc['case_sharing'] == value)
