from couchdbkit.ext.django.schema import DocumentSchema, DictProperty, DateTimeProperty
import datetime

class ComputedDocumentMixin(DocumentSchema):
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
    computed_ = DictProperty()
    computed_modified_on_ = DateTimeProperty()

    def set_definition(self, definition):
        current_namespace = self.computed_.get(definition.namespace, {})
        current_namespace[definition.slug] = dict(
            version=definition.version,
            value=definition.get_clean_value(self),
            muti_value=definition._returns_multiple,
            type=definition.doc_type
        )
        self.computed_[definition.namespace] = current_namespace
        self.computed_modified_on_ = datetime.datetime.utcnow()