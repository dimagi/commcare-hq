from __future__ import absolute_import
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.logging import notify_exception


class IndicatorAdapter(object):

    def __init__(self, config):
        self.config = config

    @memoized
    def get_table(self):
        raise NotImplementedError

    def rebuild_table(self):
        raise NotImplementedError

    def drop_table(self):
        raise NotImplementedError

    def refresh_table(self):
        raise NotImplementedError

    def get_query_object(self):
        raise NotImplementedError

    def best_effort_save(self, doc):
        """
        Does a best-effort save of the document. Will fail silently if the save is not successful.

        For certain known, expected errors this will do no additional logging.
        For unexpected errors it will log them.
        """
        raise NotImplementedError

    def handle_exception(self, doc, exception):
        notify_exception(
            None,
            u'unexpected error saving UCR doc: {}'.format(exception),
            details={
                'domain': self.config.domain,
                'doc_id': doc.get('_id', '<unknown>'),
                'table': '{} ({})'.format(self.config.display_name, self.config._id)
            }
        )

    def save(self, doc):
        """
        Saves the document. Should bubble up known errors.
        """
        raise NotImplementedError

    def delete(self, doc):
        raise NotImplementedError
