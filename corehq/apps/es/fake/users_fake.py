from corehq.pillows.user import transform_user_for_elasticsearch
from corehq.apps.es.fake.es_query_fake import HQESQueryFake


class UserESFake(HQESQueryFake):
    _all_docs = []

    def domain(self, domain):
        return self._filtered(
            lambda doc: (doc.get('domain') == domain
                         or domain in doc.get('domains', [])))

    def location(self, location_id):
        return self.term('location_id', location_id)

    def mobile_users(self):
        return self.term("doc_type", "CommCareUser")

    @classmethod
    def save_doc(cls, doc):
        doc['username.exact'] = doc.get('username', '')
        doc = transform_user_for_elasticsearch(doc)
        return super(UserESFake, cls).save_doc(doc)
