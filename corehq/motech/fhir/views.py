import json
import urllib.parse

from django.core.cache import cache
from django.http import Http404, HttpResponse, JsonResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.http import require_GET

from oauth2_provider.models import (
    get_access_token_model,
    get_refresh_token_model,
)
from oauth2_provider.views.base import AuthorizationView, TokenView

from corehq import toggles
from corehq.apps.consumer_user.decorators import consumer_user_login_required
from corehq.apps.consumer_user.models import (
    CaseRelationshipOauthToken,
    ConsumerUserCaseRelationship,
)
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.motech.exceptions import ConfigurationError
from corehq.motech.repeaters.views import AddRepeaterView, EditRepeaterView
from corehq.util.view_utils import absolute_reverse, get_case_or_404

from .const import FHIR_VERSIONS
from .decorators import smart_auth
from .forms import FHIRRepeaterForm, OAuthAllowForm
from .models import (
    FHIRResourceType,
    build_fhir_resource,
)
from .utils import (
    build_capability_statement,
    case_access_authorized,
    resource_url,
)
from .forms import FHIRRepeaterForm
from .models import FHIRResourceType, build_fhir_resource
from .utils import resource_url


class AddFHIRRepeaterView(AddRepeaterView):
    urlname = 'add_fhir_repeater'
    repeater_form_class = FHIRRepeaterForm
    page_title = _('Forward Cases to a FHIR API')
    page_name = _('Forward Cases to a FHIR API')

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    def set_repeater_attr(self, repeater, cleaned_data):
        repeater = super().set_repeater_attr(repeater, cleaned_data)
        for attr in (
            'fhir_version',
            'patient_registration_enabled',
            'patient_search_enabled',
        ):
            value = self.add_repeater_form.cleaned_data[attr]
            setattr(repeater, attr, value)
        return repeater


class EditFHIRRepeaterView(EditRepeaterView, AddFHIRRepeaterView):
    urlname = 'edit_fhir_repeater'
    page_title = _('Edit FHIR Repeater')


@require_GET
@smart_auth
@toggles.FHIR_INTEGRATION.required_decorator()
def get_view(request, domain, fhir_version_name, resource_type, resource_id):
    fhir_version = _get_fhir_version(fhir_version_name)
    if not fhir_version:
        return JsonResponse(status=400, data={'message': "Unsupported FHIR version"})

    if not case_access_authorized(domain, request.oauth_access_token, resource_id):
        return JsonResponse(status=403, data={'message': "You do not have access to this resource"})

    case = get_case_or_404(domain, resource_id)

    if not FHIRResourceType.objects.filter(
            domain=domain,
            fhir_version=fhir_version,
            name=resource_type,
            case_type__name=case.type
    ).exists():
        return JsonResponse(status=400, data={'message': "Invalid Resource Type"})
    try:
        resource = build_fhir_resource(case)
    except ConfigurationError:
        return JsonResponse(status=500, data={
            'message': 'FHIR configuration error. Please notify administrator.'
        })
    return JsonResponse(resource)


@require_GET
@smart_auth
@toggles.FHIR_INTEGRATION.required_decorator()
def search_view(request, domain, fhir_version_name, resource_type):
    fhir_version = _get_fhir_version(fhir_version_name)
    if not fhir_version:
        return JsonResponse(status=400, data={'message': "Unsupported FHIR version"})
    patient_case_id = request.GET.get('patient_id')
    if not patient_case_id:
        return JsonResponse(status=400, data={'message': "Please pass patient_id"})

    if not case_access_authorized(domain, request.oauth_access_token, patient_case_id):
        return JsonResponse(status=403, data={'message': "You do not have access to this resource"})

    case_accessor = CaseAccessors(domain)
    try:
        patient_case = case_accessor.get_case(patient_case_id)
        if patient_case.is_deleted:
            return JsonResponse(status=400, data={'message': f"Patient with ID {patient_case_id} was removed"})
    except CaseNotFound:
        return JsonResponse(status=400, data={'message': f"Could not find patient with ID {patient_case_id}"})

    case_types_for_resource_type = list(
        FHIRResourceType.objects.filter(
            domain=domain, name=resource_type, fhir_version=fhir_version
        ).values_list('case_type__name', flat=True)
    )
    if not case_types_for_resource_type:
        return JsonResponse(status=400,
                            data={'message': f"Resource type {resource_type} not available on {domain}"})

    cases = case_accessor.get_reverse_indexed_cases([patient_case_id],
                                                    case_types=case_types_for_resource_type, is_closed=False)
    response = {
        'resourceType': "Bundle",
        "type": "searchset",
        "entry": []
    }
    for case in cases:
        response["entry"].append({
            "fullUrl": resource_url(domain, fhir_version_name, resource_type, case.case_id),
            "search": {
                "mode": "match"
            }
        })
    return JsonResponse(response)


def _get_fhir_version(fhir_version_name):
    fhir_version = None
    try:
        fhir_version = [v[0] for v in FHIR_VERSIONS if v[1] == fhir_version_name][0]
    except IndexError:
        pass
    return fhir_version


@require_GET
@toggles.FHIR_INTEGRATION.required_decorator()
def smart_configuration_view(request, domain, fhir_version_name):
    return JsonResponse(
        {
            "authorization_endpoint": absolute_reverse(SmartAuthView.urlname, kwargs={"domain": domain}),
            "token_endpoint": absolute_reverse(SmartTokenView.urlname, kwargs={"domain": domain})
        }
    )


@require_GET
@toggles.FHIR_INTEGRATION.required_decorator()
def smart_metadata_view(request, domain, fhir_version_name):
    fhir_version = _get_fhir_version(fhir_version_name)
    if not fhir_version:
        return JsonResponse(status=400, data={'message': "Unsupported FHIR version"})
    return JsonResponse(build_capability_statement(domain, fhir_version))


@method_decorator([consumer_user_login_required], name="dispatch")
class SmartAuthView(AuthorizationView):
    urlname = "smart_auth_view"
    form_class = OAuthAllowForm
    template_name = "fhir/authorize.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        available_case_ids = ConsumerUserCaseRelationship.objects.filter(
            consumer_user__user=self.request.user,
            domain=self.request.domain,
        ).values_list(
            'case_id', flat=True
        ).all()
        cases = CaseAccessors(self.request.domain).get_cases(list(available_case_ids))
        kwargs['cases'] = [(case.case_id, case.name) for case in cases if case]
        return kwargs

    def get(self, request, domain, *args, **kwargs):
        if not toggles.FHIR_INTEGRATION.enabled_for_request(request):
            raise Http404()
        self._validate_case_relationships()
        return super().get(request, *args, **kwargs)

    def post(self, request, domain, *args, **kwargs):
        self._validate_case_relationships()
        response = super().post(request, *args, **kwargs)

        form = self.get_form()
        if not form.is_valid():
            return response

        if not form.cleaned_data.get("allow"):
            # The user clicked "cancel"
            return response

        case_id = request.POST.get('case_id')
        client_id = request.POST.get('client_id')
        parsed_url = urllib.parse.urlparse(response.url)
        try:
            authorization_code = urllib.parse.parse_qs(parsed_url.query)["code"][0]
        except KeyError:
            # This request didn't result in an authorization code, so just return whatever oauthlib wanted to
            return response
        else:
            # Save the selected case_id in the cache to be returned with the token in the SmartTokenView
            cache.set(_get_smart_cache_key(domain, client_id, authorization_code), case_id, 5 * 60)
            return response

    def _validate_case_relationships(self):
        if not ConsumerUserCaseRelationship.objects.filter(
            consumer_user__user=self.request.user,
            domain=self.request.domain,
        ).exists():
            raise Http404(_("There are no cases associated with this user"))


class SmartTokenView(TokenView):
    urlname = "smart_token_view"

    def post(self, request, domain, *args, **kwargs):
        if request.POST.get('grant_type') == "refresh_token":
            return self._handle_refresh_token(request, *args, **kwargs)

        response = super().post(request, *args, **kwargs)

        if response.status_code != 200:
            return response

        body = json.loads(response.content)
        access_token = body.get("access_token")
        token = get_access_token_model().objects.get(token=access_token)

        if "launch/patient" in token.scope:
            authorization_code = request.POST.get('code')
            client_id = request.POST.get('client_id')
            case_id = cache.get(_get_smart_cache_key(domain, client_id, authorization_code))
            if not case_id:
                raise Http404()

            # save the case_id in the join table. We'll check this during auth
            # later to ensure the case_id is the one this access token was made
            # for.
            if not CaseRelationshipOauthToken.create_from_case_id(case_id, token):
                return Http404()

            body['patient'] = case_id

        return HttpResponse(content=json.dumps(body), status=response.status_code)

    def _handle_refresh_token(self, request, *args, **kwargs):
        # get the previous access_token before it is revoked
        refresh_token_id = request.POST.get('refresh_token')
        refresh_token = get_refresh_token_model().objects.get(token=refresh_token_id)
        old_access_token = refresh_token.access_token

        try:
            relationship = CaseRelationshipOauthToken.objects.get(access_token=old_access_token)
        except CaseRelationshipOauthToken.DoesNotExist:
            # The old token didn't have case information, so we don't need to update anything
            return super().post(request, *args, **kwargs)
        else:
            # revoke the old access token and make a new one
            response = super().post(request, *args, **kwargs)
            body = json.loads(response.content)
            access_token = body.get("access_token")
            new_access_token = get_access_token_model().objects.get(token=access_token)

            relationship.access_token = new_access_token
            relationship.save()

            return response


def _get_smart_cache_key(domain, client_id, authorization_code):
    return f"{domain}-{client_id}-{authorization_code}"
