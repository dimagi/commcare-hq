from django.utils.decorators import method_decorator
from django.views.generic import View
from djangular.views.mixins import JSONResponseMixin, allow_remote_invocation
from corehq import toggles
from corehq.apps.domain.decorators import login_required


class NotificationsServiceRMIView(JSONResponseMixin, View):
    urlname = "notifications_service"
    http_method_names = ['post']

    @method_decorator(login_required)
    @toggles.NOTIFICATIONS.required_decorator()
    def dispatch(self, request, *args, **kwargs):
        return super(NotificationsServiceRMIView, self).dispatch(request, *args, **kwargs)

    @allow_remote_invocation
    def get_notifications(self, in_data):
        # todo pagination
        return {

        }

    @allow_remote_invocation
    def mark_as_read(self, in_data):
        # todo
        return {}
