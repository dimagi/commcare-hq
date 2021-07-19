import sys

from django.shortcuts import render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext

import requests
from requests_toolbelt.adapters import host_header_ssl

from corehq import toggles
from corehq.apps.locations.permissions import location_safe
from corehq.apps.reports.models import TableauVisualization
from corehq.apps.reports.standard import ProjectReport
from corehq.apps.reports.views import BaseProjectReportSectionView
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions


@method_decorator(require_permission(Permissions.edit_data), name='dispatch')   # TODO: is that the right perm?
@method_decorator(toggles.EMBEDDED_TABLEAU.required_decorator(), name='dispatch')
class TableauView(BaseProjectReportSectionView):    # TODO: breadcrumbs aren't showing
    urlname = 'tableau'
    page_title = "TODO"  #ugettext_noop("TODO")
    template_name = 'reports/tableau_template.html'

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


class TableauReport(ProjectReport):
    """
    Base class for all Tableau reports
    """
    base_template = 'reports/tableau_template.html'
    emailable = False
    exportable = False
    exportable_all = False
    ajax_pagination = False
    fields = []
    primary_sort_prop = None

    @property
    def template_context(self):
        context = super().template_context
        if self.visualization.server.validate_hostname == '':
            hostname = self.visualization.server.server_name
        else:
            hostname = self.visualization.server.validate_hostname
        context.update({"domain": self.visualization.server.domain,
                        "server_type": self.visualization.server.server_type,
                        "server_address": self.visualization.server.server_name,
                        "validate_hostname": hostname,
                        "target_site": self.visualization.server.target_site,
                        "allow_domain_username_override": self.visualization.server.allow_domain_username_override,
                        "domain_username": self.visualization.server.domain_username,
                        "view_url": self.visualization.view_url})
        return context

    @property
    def view_response(self):
        if self.visualization.server.server_type == 'server':
            return self.tableau_server_response()
        else:
            return self.tableau_online_response()

    def get_post_username(self):
        if self.visualization.server.allow_domain_username_override:
            tableau_trusted_auth_username = self.request.user.get('tableau_trusted_auth_username')
            if tableau_trusted_auth_username:
                return tableau_trusted_auth_username
        return self.visualization.server.domain_username

    def tableau_server_response(self):
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
                self.context.update({'ticket': tabserver_response.content.decode('utf-8')})
                return super().view_response
            else:
                self.context.update({"failure_message": ugettext("Tableau trusted authentication failed")})
                return render(self.request, 'reports/tableau_server_request_failed.html',
                              self.context)
        else:
            message = "Request to Tableau failed with status code {}".format(tabserver_response.status_code)
            self.context.update({"failure_message": ugettext(message)})
            return render(self.request, 'reports/tableau_server_request_failed.html',
                          self.context)

    def tableau_online_response(self):
        # Call the Tableau server to get a ticket.
        return super().view_response


# Making a class per visualization (and on each page load) is overkill, but
# a class is expected for items in the left nav bar, so we do that for
# expedience.
def get_reports(domain):
    result = []
    for vis_num, v in enumerate(TableauVisualization.objects.filter(domain=domain)):
        visualization_class = _make_visualization_class(vis_num, v)
        if visualization_class is not None:
            result.append(visualization_class)
    return tuple(result)


def _make_visualization_class(num, vis):
    # See _make_report_class in corehq/reports.py
    type_name = 'TableauVisualization{}'.format(num)

    view_sheet = '/'.join(vis.view_url.split('?')[0].split('/')[-2:])

    new_class = type(type_name, (TableauReport,), {
        'name': view_sheet,
        'slug': 'tableau_visualization_{}'.format(num),
        'visualization': vis,
    })
    # Make the class a module attribute
    setattr(sys.modules[__name__], type_name, new_class)
    return location_safe(new_class)
