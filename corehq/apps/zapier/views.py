import json

from django.http import HttpResponse
from django.http.response import HttpResponseBadRequest
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from django.views.generic import View

from corehq.apps.domain.decorators import login_or_api_key
from corehq.apps.zapier.queries import get_subscription_by_url
from corehq.apps.zapier.services import delete_subscription_with_url
from corehq.toggles import ZAPIER_INTEGRATION
from .models import Subscription


class SubscribeView(View):

    urlname = 'subscribe'

    @method_decorator(login_or_api_key)
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        domain = args[0]
        if not ZAPIER_INTEGRATION.enabled(domain) or not request.couch_user.is_member_of(domain):
            return HttpResponseBadRequest()
        return super(SubscribeView, self).dispatch(request, *args, **kwargs)

    def post(self, request, domain, *args, **kwargs):
        data = json.loads(request.body)
        subscription = get_subscription_by_url(domain, data['target_url'])
        if subscription:
            # https://zapier.com/developer/documentation/v2/rest-hooks/
            # Generally, subscription URLs should be unique.
            # Return a 409 status code if this criteria isn't met (IE: there is a uniqueness conflict).
            return HttpResponse(status=409)
        Subscription.objects.create(
            domain=domain,
            user_id=str(request.couch_user.get_id),
            event_name=data['event'],
            url=data['target_url'],
            form_xmlns=data['form']
        )
        return HttpResponse('OK')


class UnsubscribeView(View):

    urlname = 'unsubscribe'

    # Zapier recommends not requiring authentication for unsubscribe endpoint
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super(UnsubscribeView, self).dispatch(*args, **kwargs)

    def post(self, request, *args, **kwargs):
        data = json.loads(request.body)
        url = data['target_url']
        delete_subscription_with_url(url)
        return HttpResponse('OK')
