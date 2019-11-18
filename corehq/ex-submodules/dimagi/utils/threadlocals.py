# threadlocals middleware for global usage
try:
    from threading import local
except ImportError:
    from .django.utils._threading_local import local

_thread_locals = local()


# todo: only used in auditcare, and looks like can be removed
def get_current_user():
    return getattr(_thread_locals, 'user', None)
