from django.conf import settings


def get_formplayer_url(domain, username):
    return settings.FORMPLAYER_URL.format(
        domain=domain,
        username=username,
    )
