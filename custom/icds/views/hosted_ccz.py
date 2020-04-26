from django.conf import settings
from django.contrib import messages
from django.http import HttpResponseRedirect, JsonResponse
from django.http.response import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy, ugettext_noop
from django.views.decorators.http import require_GET
from django.views.generic import TemplateView

from couchexport.models import Format

from corehq import toggles
from corehq.apps.app_manager.dbaccessors import (
    get_brief_apps_in_domain,
    get_build_doc_by_version,
)
from corehq.apps.domain.auth import get_username_and_password_from_request
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.domain.views import BaseDomainView, DomainViewMixin
from corehq.apps.locations.permissions import location_safe
from corehq.util.download import get_download_response
from custom.icds.const import (
    DISPLAY_CHOICE_CUSTOM,
    DISPLAY_CHOICE_FOOTER,
    DISPLAY_CHOICE_LIST,
    FILE_TYPE_CHOICE_ZIP,
)
from custom.icds.forms import HostedCCZForm, HostedCCZLinkForm
from custom.icds.models import (
    HostedCCZ,
    HostedCCZCustomSupportingFile,
    HostedCCZLink,
    HostedCCZSupportingFile,
)
from custom.icds.tasks.hosted_ccz import setup_ccz_file_for_hosting
from custom.nic_compliance.utils import verify_password


@location_safe
@method_decorator([login_and_domain_required, toggles.MANAGE_CCZ_HOSTING.required_decorator()], name='dispatch')
class ManageHostedCCZLink(BaseDomainView):
    urlname = "manage_hosted_ccz_links"
    page_title = ugettext_lazy("Manage CCZ Hosting Links")
    template_name = 'icds/manage_hosted_ccz_links.html'
    section_name = ugettext_lazy("CCZ Hosting Links")

    @cached_property
    def section_url(self):
        return reverse(ManageHostedCCZLink.urlname, args=[self.domain])

    @cached_property
    def form(self):
        return HostedCCZLinkForm(
            domain=self.domain,
            data=self.request.POST if self.request.method == "POST" else None
        )

    def get_context_data(self, **kwargs):
        links = [l.to_json() for l in HostedCCZLink.objects.filter(domain=self.domain)]
        return {
            'form': self.form,
            'links': links,
            'domain': self.domain,
        }

    def delete(self):
        link_id = self.kwargs.get('link_id')
        if link_id:
            try:
                hosted_ccz_link = HostedCCZLink.objects.get(pk=link_id, domain=self.domain)
            except HostedCCZLink.DoesNotExist:
                pass
            else:
                hosted_ccz_link.delete()
                messages.success(self.request, _("Successfully removed link and all associated ccz hosting."))

    def post(self, request, *args, **kwargs):
        if self.request.POST.get('delete'):
            self.delete()
            return redirect(ManageHostedCCZLink.urlname, domain=self.domain)
        if self.form.is_valid():
            self.form.save()
            return redirect(ManageHostedCCZLink.urlname, domain=self.domain)
        return self.get(request, *args, **kwargs)


@require_GET
@toggles.MANAGE_CCZ_HOSTING.required_decorator()
def ccz_hostings_json(request, domain):
    limit = int(request.GET.get('limit', 10))
    page = int(request.GET.get('page', 1))

    if request.GET.get('link_id'):
        hosted_cczs = HostedCCZ.objects.filter(link_id=request.GET.get('link_id'))
    else:
        hosted_cczs = HostedCCZ.objects.filter(link__domain=domain)
    if request.GET.get('app_id'):
        hosted_cczs = hosted_cczs.filter(app_id=request.GET.get('app_id'))
    version = request.GET.get('version')
    if version:
        hosted_cczs = hosted_cczs.filter(version=request.GET.get('version'))
    if request.GET.get('profile_id'):
        hosted_cczs = hosted_cczs.filter(profile_id=request.GET.get('profile_id'))
    if request.GET.get('status'):
        hosted_cczs = hosted_cczs.filter(status=request.GET.get('status'))

    total = hosted_cczs.count()
    skip = (page - 1) * limit
    hosted_cczs = hosted_cczs[skip:skip + limit]
    hosted_cczs = [h.to_json() for h in hosted_cczs]

    return JsonResponse({
        'hostings': hosted_cczs,
        'total': total,
    })


class EditHostedCCZLink(ManageHostedCCZLink):
    urlname = "edit_hosted_ccz_link"

    @cached_property
    def form(self):
        link = HostedCCZLink.objects.get(id=self.kwargs['link_id'], domain=self.domain)
        if self.request.POST:
            return HostedCCZLinkForm(domain=self.domain, instance=link, data=self.request.POST)
        return HostedCCZLinkForm(domain=self.domain, instance=link)

    def get_context_data(self, **kwargs):
        return {
            'form': self.form,
            'domain': self.domain,
        }


@location_safe
@method_decorator([login_and_domain_required, toggles.MANAGE_CCZ_HOSTING.required_decorator()], name='dispatch')
class ManageHostedCCZ(BaseDomainView):
    urlname = "manage_hosted_ccz"
    page_title = ugettext_lazy("Manage CCZ Hosting")
    template_name = 'icds/manage_hosted_ccz.html'
    section_name = ugettext_noop('CCZ Hostings')

    @cached_property
    def section_url(self):
        return reverse(ManageHostedCCZ.urlname, args=[self.domain])

    @cached_property
    def form(self):
        return HostedCCZForm(
            self.request,
            self.domain,
            self.request.user.email,
            data=self.request.POST if self.request.method == "POST" else None
        )

    def _get_initial_app_profile_details(self, version):
        app_id = self.request.GET.get('app_id')
        selected_profile_id = self.request.GET.get('profile_id', '')
        # only when performing search populate these initial values
        if app_id and version:
            build_doc = get_build_doc_by_version(self.domain, self.request.GET.get('app_id'), version)
            if build_doc:
                return [{
                    'id': _id,
                    'text': details['name'],
                    'selected': selected_profile_id == _id
                } for _id, details in build_doc['build_profiles'].items()]

    def get_context_data(self, **kwargs):
        version = None      # TODO: handle search from js
        return {
            'form': self.form,
            'domain': self.domain,
            'selected_build_details': ({'id': version, 'text': version} if version else None),
            'initial_app_profile_details': self._get_initial_app_profile_details(version),
        }

    def post(self, request, *args, **kwargs):
        if self.form.is_valid():
            success, error_message = self.form.save()
            if success:
                return redirect(self.urlname, domain=self.domain)
            else:
                messages.error(request, error_message)
        return self.get(request, *args, **kwargs)


class HostedCCZView(DomainViewMixin, TemplateView):
    urlname = "hosted_ccz"
    page_title = ugettext_lazy("CCZ Hosting")
    template_name = 'icds/hosted_ccz.html'

    def get(self, request, *args, **kwargs):
        self.identifier = kwargs.get('identifier')
        try:
            hosted_ccz_link = self.hosted_ccz_link
        except HostedCCZLink.DoesNotExist:
            return HttpResponse(status=404)

        username, password = get_username_and_password_from_request(request)
        if username and password:
            if username == hosted_ccz_link.username and verify_password(password, hosted_ccz_link.password):
                return super(HostedCCZView, self).get(request, *args, **kwargs)
        # User did not provide an authorization header or gave incorrect credentials.
        response = HttpResponse(status=401)
        response['WWW-Authenticate'] = 'Basic realm="%s"' % ''
        return response

    @cached_property
    def hosted_ccz_link(self):
        return HostedCCZLink.objects.get(identifier=self.identifier)

    def get_context_data(self, **kwargs):
        return {
            'page_title': self._page_title,
            'hosted_cczs': [h.to_json() for h in HostedCCZ.objects.filter(link=self.hosted_ccz_link)
                            if h.utility.file_exists()],
            'icds_env': settings.SERVER_ENVIRONMENT in settings.ICDS_ENVS,
            'supporting_files': self._get_supporting_files(),
            'footer_files': self._get_files_for(DISPLAY_CHOICE_FOOTER),
        }

    @property
    def _page_title(self):
        return self.hosted_ccz_link.page_title or _("%s CommCare Files" % self.identifier.capitalize())

    def _get_supporting_files(self):
        supporting_files = self._get_files_for(DISPLAY_CHOICE_LIST)
        custom_supporting_files = {
            custom_file.file.file_name: self._download_link(custom_file.file.pk)
            for custom_file in HostedCCZCustomSupportingFile.objects.filter(link=self.hosted_ccz_link)
        }
        supporting_files.update(custom_supporting_files)
        return supporting_files

    def _get_files_for(self, display):
        return {
            supporting_file.file_name: self._download_link(supporting_file.pk)
            for supporting_file in HostedCCZSupportingFile.objects.filter(domain=self.domain, display=display)
        }

    def _download_link(self, pk):
        return reverse('hosted_ccz_download_supporting_files', args=[self.domain, pk])


@login_and_domain_required
def remove_hosted_ccz(request, domain, hosting_id):
    try:
        hosted_ccz = HostedCCZ.objects.get(pk=hosting_id, link__domain=domain)
        hosted_ccz.delete()
    except HostedCCZ.DoesNotExist:
        pass
    return HttpResponseRedirect(reverse(ManageHostedCCZ.urlname, args=[domain]))


@login_and_domain_required
def recreate_hosted_ccz(request, domain, hosting_id):
    try:
        hosted_ccz = HostedCCZ.objects.get(pk=hosting_id, link__domain=domain)
    except HostedCCZ.DoesNotExist:
        pass
    else:
        hosted_ccz.utility.remove_file_from_blobdb()
        hosted_ccz.update_status('pending')
        setup_ccz_file_for_hosting.delay(hosted_ccz.pk, user_email=request.user.email)
    return HttpResponseRedirect(reverse(ManageHostedCCZ.urlname, args=[domain]))


@location_safe
def download_ccz(request, domain, hosting_id):
    hosted_ccz = HostedCCZ.objects.get(pk=hosting_id, link__domain=domain)
    file_size = hosted_ccz.utility.get_file_meta().content_length
    # check for file name of the ccz hosting object first because
    # the file meta might be coming from CCZ stored for another ccz hosting instance
    # since we don't re-store already present CCZs
    file_name = hosted_ccz.file_name or hosted_ccz.utility.get_file_meta().name
    if not file_name.endswith('.ccz'):
        file_name = file_name + '.ccz'
    content_format = Format('', Format.ZIP, '', True)
    return get_download_response(hosted_ccz.utility.get_file(), file_size, content_format, file_name,
                                 request)


@location_safe
def download_ccz_supporting_files(request, domain, hosting_supporting_file_id):
    ccz_supporting_file = HostedCCZSupportingFile.objects.get(pk=hosting_supporting_file_id, domain=domain)
    ccz_utility = ccz_supporting_file.utility
    file_name = ccz_supporting_file.file_name or ccz_utility.get_file_meta().name
    if ccz_supporting_file.file_type == FILE_TYPE_CHOICE_ZIP:
        content_format = Format('', Format.ZIP, '', True)
    else:
        content_format = Format('', Format.HTML, '', True)
    file = ccz_utility.get_file()
    return get_download_response(file, file.content_length, content_format,
                                 file_name, request)
