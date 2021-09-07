from django.utils.functional import cached_property


class RegistrySchema:

    def __init__(self, schema_data):
        self.schema_data = schema_data

    @cached_property
    def case_types(self):
        return [
            case["case_type"] for case in self.schema_data
        ]


class RegistrySchemaBuilder:
    def __init__(self, case_types):
        self.case_types = case_types

    def build(self):
        return [{"case_type": type_} for type_ in self.case_types]
