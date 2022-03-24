from django.dispatch import Signal


successful_form_received = Signal()  # providing args: posted

xform_archived = Signal()  # providing args: xform
xform_unarchived = Signal()  # providing args: xform
