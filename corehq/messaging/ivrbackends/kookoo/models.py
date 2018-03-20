from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.ivr.models import SQLIVRBackend


class SQLKooKooBackend(SQLIVRBackend):
    """
    IVR Functionality has been removed, but this model is being kept
    in order to preserve foreign key references in the Call model history.
    """

    class Meta(object):
        app_label = 'sms'
        proxy = True
