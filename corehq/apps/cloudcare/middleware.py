from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth import login


class CloudcareMiddleware(object):

    def process_view(self, request, view_func, view_args, view_kwargs):
        auth_as = request.GET.get('auth_as', None)
        view_name = '.'.join((view_func.__module__, view_func.__name__))
        if request.user and request.user.is_superuser and auth_as:
            try:
                request.user = User.objects.get(username=auth_as)
            except User.DoesNotExist:
                messages.warning(request, u'Unable to find user: {} as'.format(auth_as))
            else:
                # http://stackoverflow.com/a/2787747/835696
                # This allows us to bypass the authenticate call
                request.user.backend = 'django.contrib.auth.backends.ModelBackend'
                login(request, request.user)

        return None
