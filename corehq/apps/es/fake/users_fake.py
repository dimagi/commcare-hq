from corehq.apps.es.fake.es_query_fake import ESQueryFake


class UserESFake(ESQueryFake):
    _all_docs = []

    def domain(self, domain):
        return self._filtered(
            lambda doc: (doc.get('domain') == domain
                         or domain in doc.get('domains', [])))
