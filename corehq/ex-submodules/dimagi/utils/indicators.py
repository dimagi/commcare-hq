from __future__ import absolute_import
from couchdbkit import ResourceConflict
from dimagi.ext.couchdbkit import DocumentSchema, DictProperty, DateTimeProperty, BooleanProperty
import datetime
from dimagi.utils.couch.database import get_safe_write_kwargs


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

    def update_indicator(self, indicator_def, save_on_update=True, logger=None):
        existing_indicators = self.computed_.get(indicator_def.namespace, {})
        updated_indicators, is_update = indicator_def.update_computed_namespace(existing_indicators, self)
        if is_update:
            self.computed_[indicator_def.namespace] = updated_indicators
            self.computed_modified_on_ = datetime.datetime.utcnow()
            if logger:
                logger.info("[INDICATOR %(namespace)s %(domain)s] Updating %(indicator_type)s:%(indicator_slug)s "
                            "in %(document_type)s [%(document_id)s]." % {
                                'namespace': indicator_def.namespace,
                                'domain': indicator_def.domain,
                                'indicator_type': indicator_def.__class__.__name__,
                                'indicator_slug': indicator_def.slug,
                                'document_type': self.__class__.__name__,
                                'document_id': self._id,
                            })
            if save_on_update:
                self.save(**get_safe_write_kwargs())
                if logger:
                    logger.debug("Saved %s." % self._id)
        return is_update

    def update_indicators_in_bulk(self, indicators, save_on_update=True, logger=None):
        is_update = False
        for indicator in indicators:
            try:
                if self.update_indicator(indicator, save_on_update=False, logger=logger):
                    is_update = True
            except Exception:
                logger.exception("[INDICATOR %(namespace)s %(domain)s] Failed to update %(indicator_type)s: "
                                 "%(indicator_slug)s in %(document_type)s [%(document_id)s]." % {
                                     'namespace': indicator.namespace,
                                     'domain': indicator.domain,
                                     'indicator_type': indicator.__class__.__name__,
                                     'indicator_slug': indicator.slug,
                                     'document_type': self.__class__.__name__,
                                     'document_id': self._id,
                                 })

        if is_update and save_on_update:
            try:
                self.save(**get_safe_write_kwargs())
                if logger:
                    logger.info("Saved %s." % self._id)
            except ResourceConflict:
                logger.error("[INDICATOR %(domain)s] Resource conflict failed to save document indicators for "
                             "%(document_type)s [%(document_id)s]." % {
                                 'domain': self.domain,
                                 'document_type': self.__class__.__name__,
                                 'document_id': self._id,
                             })

        return is_update

