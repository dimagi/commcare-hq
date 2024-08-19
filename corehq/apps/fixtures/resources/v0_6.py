from . import v0_1


class LookupTableItemResource(v0_1.LookupTableItemResource):

    class Meta(v0_1.LookupTableItemResource.Meta):
        always_return_data = True
