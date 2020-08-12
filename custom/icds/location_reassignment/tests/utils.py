from collections import namedtuple

Location = namedtuple('Location', ['location_id', 'site_code'])


class CommCareCaseStub(object):
    def __init__(self, case_id, name, case_json):
        self.case_id = case_id
        self.name = name
        self.case_json = case_json

    def get_case_property(self, case_property):
        return self.case_json.get(case_property)
