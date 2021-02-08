from functools import wraps
from django.contrib.auth.views import redirect_to_login
from django.urls import reverse


def login_required(view_func):
    @wraps(view_func)
    def _inner(request, *args, **kwargs):
        user = request.user
        if not (user.is_authenticated and user.is_active):
            url = reverse('login')
            return redirect_to_login(request.get_full_path(), url)

        # User's login and domain have been validated - it's safe to call the view function
        return view_func(request, *args, **kwargs)
    return _inner
