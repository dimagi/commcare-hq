from django.conf import settings

class attrdict(dict):

    def __getattr__(self, name):
        return self[name]


def get_user(name, exact=False):
    users = settings.SELENIUM_USERS
    try:
        user = users[name]
    except KeyError:
        if name == 'WEB_USER' and not exact:
            user = users['ADMIN']
        else:
            raise

    return attrdict(**user)

def get_app(name):
    defaults = getattr(settings, 'SELENIUM_APP_SETTING_DEFAULTS', {})
    user = getattr(settings, 'SELENIUM_APP_SETTINGS', {})

    app = defaults.get('all', {})
    app.update(defaults.get(name, {}))
    app.update(user.get('all', {}))
    app.update(user.get(name, {}))

    return attrdict(**app)
