from django.utils.functional import cached_property


class RegistrySchema:

    def __init__(self, schema_data):
        self.schema_data = schema_data

    @cached_property
    def case_types(self):
        return [
            case["case_type"] for case in self.schema_data
        ]
