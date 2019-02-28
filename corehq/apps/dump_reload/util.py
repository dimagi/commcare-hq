from __future__ import unicode_literals


def get_model_label(model_class):
    return '{}.{}'.format(model_class._meta.app_label, model_class.__name__)
