from __future__ import absolute_import
from __future__ import unicode_literals
from dimagi.ext.couchdbkit import DocumentSchema, DictProperty, DateTimeProperty, BooleanProperty


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
    initial_processing_complete = BooleanProperty()
