from . import v0_1


class LookupTableItemResource(v0_1.LookupTableItemResource):

    class Docs:
        summary = 'Lookup Table Items (v2)'
        description = (
            'List, create, update or delete the rows (items) of a '
            'lookup table in a project space. Version 2 returns the '
            'created or updated row in the response body for write '
            'requests.'
        )

    class Meta(v0_1.LookupTableItemResource.Meta):
        always_return_data = True
