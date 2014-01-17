from django.http import Http404
from functools import wraps

from toggle import shortcuts


def require_toggle(toggle_slug):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            if not hasattr(request, 'user') or not shortcuts.toggle_enabled(toggle_slug, request.user.username):
                raise Http404()
            return view_func(request, *args, **kwargs)
        return wrapped_view
    return decorator
