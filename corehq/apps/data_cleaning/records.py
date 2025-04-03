from corehq.apps.hqwebapp.tables.elasticsearch.records import CaseSearchElasticRecord


class EditableCaseSearchElasticRecord(CaseSearchElasticRecord):

    def __init__(self, record, request, **kwargs):
        super().__init__(record, request, **kwargs)
        self.session = kwargs.pop('session')

    def __getitem__(self, item):
        return super().__getitem__(item)
