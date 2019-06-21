from __future__ import absolute_import
from __future__ import unicode_literals
from django.dispatch import Signal

"""
When an xform is received, either from posting or when finished playing.
"""
xform_received = Signal(providing_args=["form"])

"""
When a form is finished playing (via the SMS apis)
"""
sms_form_complete = Signal(providing_args=["session_id", "form"])
