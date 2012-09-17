from couchdbkit.ext.django.schema import DocumentSchema, DictProperty, DateTimeProperty

class IndicatorDocumentMixin(DocumentSchema):
    """
        Use this mixin for things like CommCareCase or XFormInstance documents that take advantage
        of indicator definitions.

        _computed is namespaced and may look like the following for indicators:
        _computed: {
            mvp_indicators: {
                indicator_slug: {
                    version: 1,
                    value: "foo"
                }
            }
        }
    """
    _computed = DictProperty()
    _computed_modified_on = DateTimeProperty()