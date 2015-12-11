from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.generic import View
from corehq.apps.domain.decorators import login_required
from corehq.apps.tour.models import GuidedTour


class EndTourView(View):
    urlname = 'end_js_tour'
    http_method_names = ['post']

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        return super(EndTourView, self).dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        GuidedTour.mark_as_seen(request.user, kwargs['tour_slug'])
        return HttpResponse("success")
