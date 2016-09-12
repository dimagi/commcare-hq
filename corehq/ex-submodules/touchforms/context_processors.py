from django.conf import settings

def meta(request):
    return {
        'app_version': settings.REVISION if settings.REVISION else settings.RELEASE_VERSION,
    }

def static_workaround(request):
    return {
        # hack for django staticfiles + couchlog support
        # if you don't have django-staticfiles installed add this to your 
        # context processors:
        # "touchforms.context_processors.static_workaround",
        "STATIC_URL": "%s%s" % (settings.MEDIA_URL, "formplayer/")
    }
