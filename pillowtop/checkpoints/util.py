import os


def get_machine_id(settings_override=None):
    """
    Gets a machine ID based on settings or os information
    """
    if settings_override and hasattr(settings_override, 'PILLOWTOP_MACHINE_ID'):
        os_name = getattr(settings_override, 'PILLOWTOP_MACHINE_ID')
    elif hasattr(os, 'uname'):
        os_name = os.uname()[1].replace('.', '_')
    else:
        os_name = 'unknown_os'
    return os_name
