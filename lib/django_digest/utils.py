from django.conf import settings

DEFAULT_REALM = 'DJANGO'

def get_setting(setting_name, default=None):
    if hasattr(settings, setting_name):
        return getattr(settings, setting_name)
    else:
        return default

def get_backend(setting_name, default_backend_class_path):
    path = get_setting(setting_name, default_backend_class_path)

    from django.core import exceptions
    from django.utils.importlib import import_module

    path_components = path.rsplit('.', 1)
    if not len(path_components) == 2:
        raise exceptions.ImproperlyConfigured('%s isn\'t a classname' % path)
    try:
        mod = import_module(path_components[0])
    except ImportError, e:
        raise exceptions.ImproperlyConfigured('Error importing module %s: "%s"' %
                                              (path_components[0], e))

    try:
        cls = getattr(mod, path_components[1])
    except AttributeError:
        raise exceptions.ImproperlyConfigured('module "%s" does not define a "%s" class' %
                                              (path_components[0], path_components[1]))

    return cls()
