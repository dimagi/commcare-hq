from django.dispatch import Signal


successful_form_received = Signal(providing_args=["posted"])

xform_archived = Signal(providing_args=["xform"])
xform_unarchived = Signal(providing_args=["xform"])
