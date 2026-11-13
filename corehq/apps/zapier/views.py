import json

from django.http import HttpResponse
from django.http.response import HttpResponseBadRequest, HttpResponseForbidden
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View

from dimagi.utils.web import json_response

from corehq import privileges
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.app_manager.models import Application
from corehq.apps.domain.decorators import login_or_api_key
from corehq.apps.zapier.consts import CASE_TYPE_REPEATER_CLASS_MAP, EventTypes
from corehq.apps.zapier.queries import get_subscription_by_url
from corehq.apps.zapier.services import delete_subscription_with_url

from .models import ZapierSubscription


class SubscribeView(View):

    urlname = 'zapier_subscribe'

    @method_decorator(login_or_api_key)
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        domain = args[0]
        if not domain_has_privilege(domain, privileges.ZAPIER_INTEGRATION)\
                or not request.couch_user.is_member_of(domain):
            return HttpResponseForbidden()
        return super(SubscribeView, self).dispatch(request, *args, **kwargs)

    def post(self, request, domain, *args, **kwargs):
        data = json.loads(request.body.decode('utf-8'))

        subscription = get_subscription_by_url(domain, data['target_url'])
        if subscription:
            # https://zapier.com/developer/documentation/v2/rest-hooks/
            # Generally, subscription URLs should be unique.
            # Return a 409 status code if this criteria isn't met (IE: there is a uniqueness conflict).
            return HttpResponse(status=409)

        if data['event'] == EventTypes.NEW_FORM:
            application = Application.get(data['application'])
            if not application or not application.get_forms_by_xmlns(data['form']):
                return HttpResponse(status=400)
            subscription = ZapierSubscription.objects.create(
                domain=domain,
                user_id=str(request.couch_user.get_id),
                event_name=data['event'],
                url=data['target_url'],
                application_id=data['application'],
                form_xmlns=data['form'],
            )
        elif data['event'] in CASE_TYPE_REPEATER_CLASS_MAP:
            subscription = ZapierSubscription.objects.create(
                domain=domain,
                user_id=str(request.couch_user.get_id),
                event_name=data['event'],
                url=data['target_url'],
                case_type=data['case_type'],
            )
        else:
            return HttpResponseBadRequest()

        # respond with the ID so that zapier can use it to unsubscribe
        return json_response({'id': subscription.id})


class UnsubscribeView(View):

    urlname = 'zapier_unsubscribe'

    # Zapier recommends not requiring authentication for unsubscribe endpoint
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super(UnsubscribeView, self).dispatch(*args, **kwargs)

    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body.decode('utf-8'))
        except ValueError:
            return HttpResponseBadRequest()
        url = data.get('target_url')
        if not url:
            return HttpResponseBadRequest()
        delete_subscription_with_url(url)
        return HttpResponse('OK')
