from couchdbkit.ext.django.schema import DocumentSchema, DictProperty, DateTimeProperty, BooleanProperty
import datetime

class ComputedDocumentMixin(DocumentSchema):
    """
        Use this mixin for things like CommCareCase or XFormInstance documents that take advantage
        of indicator definitions.

        computed_ is namespaced and may look like the following for indicators:
        computed_: {
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

    # a flag for the indicator pillows so that there aren't any Document Update Conflicts
    initial_processing_complete = BooleanProperty(default=False)

    def update_indicator(self, indicator_def, save_on_update=True):
        existing_indicators = self.computed_.get(indicator_def.namespace, {})
        updated_indicators, is_update = indicator_def.update_computed_namespace(existing_indicators, self)
        if is_update:
            self.computed_[indicator_def.namespace] = updated_indicators
            self.computed_modified_on_ = datetime.datetime.utcnow()
            if save_on_update:
                self.save()
        return is_update
