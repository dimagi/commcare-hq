from __future__ import absolute_import
from __future__ import unicode_literals

from django.http import HttpResponseRedirect
from django.utils.translation import (
    ugettext_lazy,
    ugettext_noop,
    ugettext as _,
)
from django.utils.functional import cached_property
from django.utils.decorators import method_decorator
from django.urls import reverse
from django.shortcuts import redirect
from django.views.generic import TemplateView
from django.contrib import messages
from django.http import HttpResponse
from django.conf import settings

from couchexport.models import Format
from corehq import toggles
from corehq.apps.domain.auth import get_username_and_password_from_request
from corehq.apps.app_manager.dbaccessors import (
    get_brief_apps_in_domain,
    get_build_doc_by_version,
)
from corehq.apps.domain.views import (
    BaseDomainView,
    DomainViewMixin,
)
from corehq.apps.locations.permissions import location_safe
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.util.download import get_download_response
from custom.icds.const import (
    DISPLAY_CHOICE_LIST,
    DISPLAY_CHOICE_FOOTER,
    FILE_TYPE_CHOICE_ZIP,
)
from custom.icds.forms import (
    HostedCCZForm,
    HostedCCZLinkForm,
)
from custom.icds.models import (
    HostedCCZLink,
    HostedCCZ,
    HostedCCZSupportingFile,
)
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
        app_names = {app.id: app.name for app in get_brief_apps_in_domain(self.domain, include_remote=True)}
        if self.request.GET.get('link_id'):
            hosted_cczs = HostedCCZ.objects.filter(link_id=self.request.GET.get('link_id'))
        else:
            hosted_cczs = HostedCCZ.objects.filter(link__domain=self.domain)
        if self.request.GET.get('app_id'):
            hosted_cczs = hosted_cczs.filter(app_id=self.request.GET.get('app_id'))
        version = self.request.GET.get('version')
        if version:
            hosted_cczs = hosted_cczs.filter(version=self.request.GET.get('version'))
        if self.request.GET.get('profile_id'):
            hosted_cczs = hosted_cczs.filter(profile_id=self.request.GET.get('profile_id'))
        hosted_cczs = [h.to_json(app_names) for h in hosted_cczs]
        return {
            'form': self.form,
            'domain': self.domain,
            'hosted_cczs': hosted_cczs,
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

    @cached_property
    def hosted_ccz_link(self):
        return HostedCCZLink.objects.get(identifier=self.identifier)

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

    @property
    def _page_title(self):
        return self.hosted_ccz_link.page_title or _("%s CommCare Files" % self.identifier.capitalize())

    def _get_files_for(self, display):
        return {
            supporting_file.file_name: reverse('hosted_ccz_download_supporting_files',
                                               args=[supporting_file.domain, supporting_file.pk])
            for supporting_file in HostedCCZSupportingFile.objects.filter(domain=self.domain, display=display)
        }

    def get_context_data(self, **kwargs):
        app_names = {app.id: app.name for app in get_brief_apps_in_domain(self.domain, include_remote=True)}
        return {
            'page_title': self._page_title,
            'hosted_cczs': [h.to_json(app_names) for h in HostedCCZ.objects.filter(link=self.hosted_ccz_link)
                            if h.utility.file_exists()],
            'icds_env': settings.SERVER_ENVIRONMENT in settings.ICDS_ENVS,
            'supporting_list_files': self._get_files_for(DISPLAY_CHOICE_LIST),
            'supporting_footer_files': self._get_files_for(DISPLAY_CHOICE_FOOTER),
        }


@login_and_domain_required
def remove_hosted_ccz(request, domain, hosting_id):
    try:
        hosted_ccz = HostedCCZ.objects.get(pk=hosting_id, link__domain=domain)
        hosted_ccz.delete()
    except HostedCCZ.DoesNotExist:
        pass
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
    return get_download_response(ccz_utility.get_file(), ccz_utility.get_file_size(), content_format,
                                 file_name, request)
