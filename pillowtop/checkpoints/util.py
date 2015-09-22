import os
from django.conf import settings


def get_machine_id():
    """
    Gets a machine ID based on settings or os information
    """
    if hasattr(settings, 'PILLOWTOP_MACHINE_ID'):
        os_name = getattr(settings, 'PILLOWTOP_MACHINE_ID')
    elif hasattr(os, 'uname'):
        os_name = os.uname()[1].replace('.', '_')
    else:
        os_name = 'unknown_os'
    return os_name


def construct_checkpoint_doc_id_from_name(name):
    return "pillowtop_%s" % name
