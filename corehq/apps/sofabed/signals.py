from couchforms.signals import xform_archived
from django.core.exceptions import ObjectDoesNotExist
from corehq.apps.sofabed.models import FormData

def delete_formref(sender, xform, *args, **kwargs):
    try:
        form = FormData.objects.get(instance_id=xform.get_id)
        form.delete()
    except ObjectDoesNotExist:
        pass

xform_archived.connect(delete_formref)