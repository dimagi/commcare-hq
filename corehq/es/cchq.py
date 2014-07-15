class HQESQuery(ESQuery):
    """
    Query logic specific to CommCareHQ
    """
    def doc_type(self, doc_type):
        return self.term('doc_type', doc_type)

    def domain(self, domain):
        return self.term('domain.exact', domain)


