from touchforms.formplayer.models import XForm
from django.conf import settings
import os

def get_xform_by_namespace(namespace):
    matches = XForm.objects.filter(namespace=namespace).order_by("-version", "-created")
    if matches.count() > 0:
        return matches[0]
    else:
        raise Exception("No XForm found! The database entry was " \
                        "deleted. Please syncdb and restart the server.")


def get_autocomplete_dir():
    if hasattr(settings, "TOUCHFORMS_AUTOCOMPL_DATA_DIR"):
        return settings.TOUCHFORMS_AUTOCOMPL_DATA_DIR
    else:
        root_dir = os.path.dirname(os.path.abspath(os.path.dirname(__file__)))
        os.path.join(root_dir, 'static', 'census')
