BOOTSTRAP_2 = 'bootstrap-2'
BOOTSTRAP_3 = 'bootstrap-3'


def bootstrap_version(request):
    if hasattr(request, 'preview_bootstrap3') and request.preview_bootstrap3:
        return BOOTSTRAP_3
    return BOOTSTRAP_2
