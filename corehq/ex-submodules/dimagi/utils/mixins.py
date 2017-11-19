from __future__ import absolute_import
import six
class UnicodeMixIn(object):
    """
    Override objects so that str calls unicode and you only have to override
    unicode.
    """
    
    def __str__(self):
        return six.text_type(self).encode('utf-8')
    
    def __unicode__(self):
        # avoid recursion when we forget to override this
        return super(UnicodeMixIn, self).__str__()
