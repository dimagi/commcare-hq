from django.utils.functional import cached_property

REGISTRY_JSON_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "case_type": {
                "type": "string",
                "description": "The case type of the case"
            }
        },
        "required": ["case_type"]
    }
}


class RegistrySchema:

    def __init__(self, schema_data):
        self.schema_data = schema_data or []

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
