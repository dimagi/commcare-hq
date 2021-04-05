from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.urls import reverse

from corehq.apps.consumer_user.models import ConsumerUser


def consumer_user_login_required(view_func):

    @wraps(view_func)
    def _inner(request, *args, **kwargs):
        user = request.user
        if not (user.is_authenticated and user.is_active and ConsumerUser.objects.get_or_none(user=user)):
            url = reverse('consumer_user:login')
            return redirect_to_login(request.get_full_path(), url)

        # User login validated and verified corresponding ConsumerUser exists- it's safe to call the view function
        return view_func(request, *args, **kwargs)

    return _inner
