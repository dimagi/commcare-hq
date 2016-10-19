import json

from django.http import HttpResponse
from django.http.response import HttpResponseForbidden
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from django.views.generic import View

from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.app_manager.models import Application
from corehq.apps.domain.decorators import login_or_api_key
from corehq.apps.zapier.queries import get_subscription_by_url
from corehq.apps.zapier.services import delete_subscription_with_url
from corehq import privileges

from .models import ZapierSubscription


class SubscribeView(View):

    urlname = 'subscribe'

    @method_decorator(login_or_api_key)
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        domain = args[0]
        if not domain_has_privilege(domain, privileges.ZAPIER_INTEGRATION)\
                or not request.couch_user.is_member_of(domain):
            return HttpResponseForbidden()
        return super(SubscribeView, self).dispatch(request, *args, **kwargs)

    def post(self, request, domain, *args, **kwargs):
        data = json.loads(request.body)
        application = Application.get(docid=data['application'])
        if not application or not application.get_form_by_xmlns(data['form']):
            return HttpResponse(status=400)

        subscription = get_subscription_by_url(domain, data['target_url'])
        if subscription:
            # https://zapier.com/developer/documentation/v2/rest-hooks/
            # Generally, subscription URLs should be unique.
            # Return a 409 status code if this criteria isn't met (IE: there is a uniqueness conflict).
            return HttpResponse(status=409)

        ZapierSubscription.objects.create(
            domain=domain,
            user_id=str(request.couch_user.get_id),
            event_name=data['event'],
            url=data['target_url'],
            application_id=data['application'],
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
        try:
            data = json.loads(request.body)
        except ValueError:
            return HttpResponse(status=400)
        url = data.get('target_url')
        if not url:
            return HttpResponse(status=400)
        delete_subscription_with_url(url)
        return HttpResponse('OK')
