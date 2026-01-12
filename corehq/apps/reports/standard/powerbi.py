from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _, gettext_lazy
from django.views.decorators.http import require_POST

from no_exceptions.exceptions import Http403
import requests

from corehq.apps.reports.models import PowerBIWorkspace, PowerBIReport, PowerBIApp
from corehq.apps.reports.exceptions import PowerBIAPIError
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.domain.views.base import BaseDomainView
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.locations.permissions import location_safe


@location_safe
class PowerBIView(BaseDomainView):
    urlname = 'powerbi'
    template_name = 'reports/bootstrap5/powerbi_template.html'

    section_name = gettext_lazy("PowerBI Reports")

    @property
    def section_url(self):
        return reverse('reports_home', args=(self.domain, ))

    @property
    def page_title(self):
        return self.report.name

    @property
    def report(self):
        try:
            return PowerBIReport.objects.get(domain=self.domain, id=self.kwargs.get("report_id"))
        except PowerBIReport.DoesNotExist:
            return None

    @property
    def page_url(self):
        return reverse(self.urlname, args=(self.domain, self.report.id,))

    @method_decorator(use_bootstrap5)
    @method_decorator(login_and_domain_required)
    def dispatch(self, request, *args, **kwargs):
        if not self._authenticate_request(request):
            raise Http403
        if self.report is None:
            raise Http404()
        return super().dispatch(request, *args, **kwargs)

    def _authenticate_request(self, request):
        return request.couch_user.can_view_powerbi_report(self.domain, self.report)

    @property
    def page_context(self):
        return {
            "domain": self.report.workspace.domain,
            "workspace_id": self.report.workspace.workspace_id,
            "report_sql_id": self.report.id,
            "report_title": self.report.title,
        }

    def get(self, request, *args, **kwargs):
        return render(self.request, self.template_name, self.get_context_data())


@login_and_domain_required
@require_POST
@location_safe
def get_powerbi_embed_token(request, domain):
    """
    Generate a PowerBI embed token for a specific report.
    This endpoint is called by the frontend to get credentials for embedding.
    """
    report_data = {data: value[0] for data, value in dict(request.POST).items()}
    try:
        report = PowerBIReport.objects.get(id=report_data.get('report_sql_id'))
    except PowerBIReport.DoesNotExist:
        return JsonResponse({
            "success": False,
            "message": _("PowerBI report not found"),
        })
    # Authenticate user
    if not request.couch_user.can_view_powerbi_report(domain, report):
        raise Http403

    workspace = report.workspace

    try:
        app = PowerBIApp.objects.get(workspace=workspace)
    except PowerBIApp.DoesNotExist:
        return JsonResponse({
            "success": False,
            "message": _("PowerBI application credentials not configured for this workspace"),
        })

    try:
        # Get Azure AD access token
        access_token = app.get_access_token()

        # Generate embed token for the report
        embed_token_url = f'{workspace.api_endpoint}/v1.0/myorg/GenerateToken'

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {access_token}'
        }

        # Request body for embed token generation
        body = {
            'reports': [{'id': report.report_id}],
            'targetWorkspaces': [{'id': workspace.workspace_id}]
        }

        response = requests.post(embed_token_url, json=body, headers=headers)
        response.raise_for_status()

        embed_data = response.json()

        # Get embed URL if not cached
        embed_url = report.embed_url
        if not embed_url:
            # Fetch report details to get embed URL
            report_url = f'{workspace.api_endpoint}/v1.0/myorg/groups/{workspace.workspace_id}/reports/{report.report_id}'
            report_response = requests.get(report_url, headers=headers)
            report_response.raise_for_status()
            embed_url = report_response.json().get('embedUrl', '')

            # Cache the embed URL
            if embed_url:
                report.embed_url = embed_url
                report.save()

        return JsonResponse({
            "success": True,
            "embedToken": embed_data.get('token'),
            "embedUrl": embed_url,
            "reportId": report.report_id,
        })

    except PowerBIAPIError as e:
        return JsonResponse({
            "success": False,
            "message": _("PowerBI authentication failed: {}").format(str(e)),
        })
    except requests.exceptions.RequestException as e:
        return JsonResponse({
            "success": False,
            "message": _("PowerBI API request failed: {}").format(str(e)),
        })
