from __future__ import absolute_import
from __future__ import unicode_literals
import json

from django.http import HttpResponse
from django.http.response import HttpResponseForbidden, HttpResponseBadRequest
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from django.views.generic import View

from casexml.apps.case.mock import CaseFactory

from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.app_manager.models import Application
from corehq.apps.domain.decorators import login_or_api_key
from corehq.util.view_utils import get_case_or_404
from corehq.apps.users.models import CommCareUser
from corehq.apps.zapier.queries import get_subscription_by_url
from corehq.apps.zapier.services import delete_subscription_with_url
from corehq.apps.zapier.consts import EventTypes, CASE_TYPE_REPEATER_CLASS_MAP
from corehq import privileges
from dimagi.utils.web import json_response

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


class ZapierCreateCase(View):

    urlname = 'zapier_create_case'

    @method_decorator(login_or_api_key)
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        domain = args[0]
        if not domain_has_privilege(domain, privileges.ZAPIER_INTEGRATION):
            return HttpResponseForbidden()
        return super(ZapierCreateCase, self).dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        domain = request.GET.get('domain')
        case_type = request.GET.get('case_type')
        owner_id = request.GET.get('owner_id')
        properties = json.loads(request.body.decode('utf-8'))
        case_name = properties.pop('case_name')
        user_name = request.GET.get('user')

        if not case_type or not owner_id or not domain or not case_name:
            return HttpResponseBadRequest('Please fill in all required fields')

        couch_user = CommCareUser.get_by_username(user_name)
        if not couch_user.is_member_of(domain):
            return HttpResponseForbidden("This user does not have access to this domain.")

        factory = CaseFactory(domain=domain)
        new_case = factory.create_case(
            case_type=case_type,
            owner_id=owner_id,
            case_name=case_name,
            update=properties
        )

        return HttpResponse("Created case with id {case_id}".format(case_id=str(new_case.case_id)))


class ZapierUpdateCase(View):

    urlname = 'zapier_update_case'

    @method_decorator(login_or_api_key)
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        domain = args[0]
        if not domain_has_privilege(domain, privileges.ZAPIER_INTEGRATION):
            return HttpResponseForbidden()
        return super(ZapierUpdateCase, self).dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        domain = request.GET.get('domain')
        case_type = request.GET.get('case_type')
        user_name = request.GET.get('user')
        properties = json.loads(request.body.decode('utf-8'))
        case_id = properties['case_id']

        properties.pop('case_id')

        couch_user = CommCareUser.get_by_username(user_name)
        if not couch_user.is_member_of(domain):
            return HttpResponseForbidden("This user does not have access to this domain.")

        case = get_case_or_404(domain, case_id)

        if not case.type == case_type:
            return HttpResponseBadRequest("Case type mismatch")

        factory = CaseFactory(domain=domain)
        factory.update_case(
            case_id=case_id,
            update=properties
        )

        return HttpResponse("Case {case_id} updated".format(case_id=case_id))
