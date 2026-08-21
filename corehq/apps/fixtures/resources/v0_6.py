from . import v0_1


class LookupTableItemResource(v0_1.LookupTableItemResource):

    class Docs:
        summary = 'Lookup Table Items (v2)'
        description = (
            'List, create, update or delete the rows (items) of a '
            'lookup table in a project space. Version 2 returns the '
            'created or updated row in the response body for write '
            'requests. On update, `data_type_id` must always be '
            'included; if the request body includes neither `fields` '
            'nor `item_attributes`, the row is left unmodified.'
        )

    class Meta(v0_1.LookupTableItemResource.Meta):
        always_return_data = True
