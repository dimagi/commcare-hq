try:
    from django.template.base import TokenType
except ImportError:
    from django.template.base import TOKEN_TEXT

    # Minimal shim for what we actually use in the code.
    # Not intended to be a complete backport
    class TokenType(object):
        TEXT = TOKEN_TEXT

__all__ = ['TokenType']
