from django.conf import settings

def get_meta(request):
    return {
        'HTTP_X_FORWARDED_FOR': request.META.get('HTTP_X_FORWARDED_FOR'),
        'REMOTE_ADDR': request.META.get('REMOTE_ADDR'),
    }


def get_instance_string():
    instance = settings.ANALYTICS_CONFIG.get('HQ_INSTANCE', '')
    env = '' if instance == 'www' else instance + '_'
    return env
