from dimagi.ext.couchdbkit import Document, StringProperty
from dimagi.utils.couch.cache import cache_core


class Dhis2Connection(Document):
    domain = StringProperty()
    server_url = StringProperty()
    username = StringProperty()
    password = StringProperty()

    @classmethod
    def for_domain(cls, domain):
        res = cache_core.cached_view(
            cls.get_db(),
            "by_domain_doc_type_date/view",
            key=[domain, 'Dhis2Connection', None],
            reduce=False,
            include_docs=True,
            wrapper=cls.wrap)
        return res[0] if len(res) > 0 else None
