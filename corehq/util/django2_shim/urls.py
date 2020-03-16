try:
    from django.urls import URLResolver
except ImportError:
    from django.urls import RegexURLResolver as URLResolver


__all__ = ['URLResolver']
