from django.conf import settings


def es_index(index):
    prefix = '' if not settings.UNIT_TESTING else 'test_'
    return "{}{}".format(prefix, index)
