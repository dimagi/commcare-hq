from django.dispatch import Signal

"""
When an xform is received, either from posting or when finished playing.
"""
xform_received = Signal()  # providing args: form

"""
When a form is finished playing (via the SMS apis)
"""
sms_form_complete = Signal()  # providing args: session_id, form
