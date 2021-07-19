import sys

from django.shortcuts import render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _, ugettext_lazy

import requests
from requests_toolbelt.adapters import host_header_ssl

from corehq import toggles
from corehq.apps.reports.models import TableauVisualization
from corehq.apps.reports.views import BaseProjectReportSectionView


@method_decorator(toggles.EMBEDDED_TABLEAU.required_decorator(), name='dispatch')
class TableauView(BaseProjectReportSectionView):
    urlname = 'tableau'
    template_name = 'reports/tableau_template.html'

    # Override BaseProjectReportSectionView, but it'll still link to reports home
    section_name = ugettext_lazy("Tableau Reports")

    @property
    def page_title(self):
        return self.visualization.name

    @property
    def visualization(self):
        return TableauVisualization.objects.get(domain=self.domain, id=self.kwargs.get("viz_id"))

    @property
    def page_url(self):
        return reverse(self.urlname, args=(self.domain, self.visualization.id,))

    @property
    def page_context(self):
        if self.visualization.server.validate_hostname == '':
            hostname = self.visualization.server.server_name
        else:
            hostname = self.visualization.server.validate_hostname
        return {
            "domain": self.visualization.server.domain,
            "server_type": self.visualization.server.server_type,
            "server_address": self.visualization.server.server_name,
            "validate_hostname": hostname,
            "target_site": self.visualization.server.target_site,
            "allow_domain_username_override": self.visualization.server.allow_domain_username_override,
            "domain_username": self.visualization.server.domain_username,
            "view_url": self.visualization.view_url,
        }

    def get(self, request, *args, **kwargs):
        if self.visualization.server.server_type == 'server':
            return self.tableau_server_response()
        return super().get(request, *args, **kwargs)

    def get_post_username(self):
        if self.visualization.server.allow_domain_username_override:
            tableau_trusted_auth_username = self.request.user.get('tableau_trusted_auth_username')
            if tableau_trusted_auth_username:
                return tableau_trusted_auth_username
        return self.visualization.server.domain_username

    def tableau_server_response(self):
        context = self.page_context
        tabserver_url = 'https://{}/trusted/'.format(self.visualization.server.server_name)
        post_arguments = {'username': self.get_post_username()}
        if self.visualization.server.target_site != 'Default':
            post_arguments.update({'target_site': self.visualization.server.target_site})

        if self.visualization.server.validate_hostname != '':
            request = requests.Session()
            request.mount('https://', host_header_ssl.HostHeaderSSLAdapter())
            tabserver_response = request.post(tabserver_url,
                                              post_arguments,
                                              headers={'Host': self.visualization.server.validate_hostname})
        else:
            tabserver_response = requests.post(tabserver_url, post_arguments)

        if tabserver_response.status_code == 200:
            if tabserver_response.content != b'-1':
                context.update({'ticket': tabserver_response.content.decode('utf-8')})
                return render(self.request, self.template_name, context)
            else:
                context.update({"failure_message": _("Tableau trusted authentication failed")})
                return render(self.request, 'reports/tableau_server_request_failed.html', context)
        else:
            message = _("Request to Tableau failed with status code {}").format(tabserver_response.status_code)
            context.update({"failure_message": message})
            return render(self.request, 'reports/tableau_server_request_failed.html', context)
