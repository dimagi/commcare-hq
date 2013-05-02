from django.conf import settings

def deidentify_app(doctransform):
    """
    Deidentifies apps. Currently by allowing you to specify the name.
    """
    assert(doctransform.doc["doc_type"] == "Application")
    if hasattr(settings, "DOMAIN_SYNC_APP_NAME_MAP"):
        if doctransform.doc["name"] in settings.DOMAIN_SYNC_APP_NAME_MAP:
            doctransform.doc["name"] = settings.DOMAIN_SYNC_APP_NAME_MAP[doctransform.doc["name"]]
    return doctransform
    