from django.apps import apps

from corehq.apps.dump_reload.exceptions import DomainDumpError


def get_model_label(model_class):
    return '{}.{}'.format(model_class._meta.app_label, model_class.__name__)


def get_model_class(model_label):
    app_label, model_label = model_label.split('.')
    try:
        app_config = apps.get_app_config(app_label)
    except LookupError:
        raise DomainDumpError("Unknown application: %s" % app_label)

    try:
        model = app_config.get_model(model_label)
    except LookupError:
        raise DomainDumpError("Unknown model: %s.%s" % (app_label, model_label))

    return app_config, model
