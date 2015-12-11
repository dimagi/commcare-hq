from corehq.apps.es.fake.es_query_fake import HQESQueryFake


class UserESFake(HQESQueryFake):
    _all_docs = []

    def domain(self, domain):
        return self._filtered(
            lambda doc: (doc.get('domain') == domain
                         or domain in doc.get('domains', [])))
