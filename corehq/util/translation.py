from django.utils import translation


class localize(object):
    """
    Switch django's localization to some other language temporarily
    Usage:

    >>> _ = lambda a: 'hola' # fake for doctest
    >>> with localize('es'):
    ...     print _('hello')
    hola
    """

    def __init__(self, language):
        self.language = language

    def __enter__(self):
        self.default_language = translation.get_language()
        translation.activate(self.language or self.default_language)

    def __exit__(self, exc_type, exc_val, exc_tb):
        translation.activate(self.default_language)
