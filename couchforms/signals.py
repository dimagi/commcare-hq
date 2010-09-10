from django.dispatch import Signal

xform_saved = Signal(providing_args=["form"])

def post_form_to_couch(sender, instance, **kwargs):
    """
    When XForms are received, post them to couch.
    """
    from couchforms.util import post_xform_to_couch
    doc = post_xform_to_couch(instance)
    # fire another signal, this time saying the document was posted
    xform_saved.send(sender="post", form=doc)
    
# maybe hook this up to the xforms_received signal, for 
# now it lives on its own
# xform_received.connect(post_form_to_couch)
            