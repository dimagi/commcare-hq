from django.dispatch import Signal

xform_saved = Signal(providing_args=["xform"])
xform_archived = Signal(providing_args=["xform"])

# it's not really an xform, but many tools want to treat 
# these similarly to forms
submission_error_received = Signal(providing_args=["xform"])
