import sys

import requests

from django.shortcuts import render

from corehq.apps.locations.permissions import location_safe
from corehq.apps.domain.decorators import (
    cls_to_view,
    login_and_domain_required,
)
from corehq.apps.reports.standard import (
    ProjectReport,
)

from corehq.apps.reports.models import TableauVisualization

cls_to_view_login_and_domain = cls_to_view(additional_decorator=login_and_domain_required)


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
        context.update({"server_type": self.visualization.server.server_type,
                        "server_address": self.visualization.server.server_name,
                        "target_site": self.visualization.server.target_site,
                        "view_url": self.visualization.view_url})
        return context

    @property
    def view_response(self):
        if self.visualization.server.server_type == 'server':
            return self.tableau_server_response()
        else:
            return self.tableau_online_response()

    def tableau_server_response(self):
        # Call the Tableau server to get a ticket.
        tabserver_url = 'https://{}/trusted/'.format(self.visualization.server.server_name)
        # The verify argument indicates that we trust the self-signed certificate
        # which lets SSL connections succeed. It should not be used in production.
        post_arguments = {'username': self.request.user.username}
        if self.visualization.server.target_site != 'Default':
            post_arguments.update({'target_site': self.visualization.server.target_site})
        tabserver_response = requests.post(tabserver_url,
                                           post_arguments,
                                           verify='corehq/apps/reports/standard/CA_BUNDLE')
        if tabserver_response.status_code == 200:
            if tabserver_response.content != b'-1':
                self.context.update({'ticket': tabserver_response.content.decode('utf-8')})
                return super().view_response
            else:
                return render(self.request, 'reports/tableau_auth_failed.html',
                              self.context)
        else:
            self.context.update({"status_code": tabserver_response.status_code})
            return render(self.request, 'reports/tableau_request_failed.html',
                          self.context)

    def tableau_online_response(self):
        # Call the Tableau server to get a ticket.
        return super().view_response


# Making a class per visualization (and on each page load) is overkill, but
# a class is expected for items in the left nav bar, so we do that for
# expedience.
def get_reports(domain):
    vis_num = 1
    result = []
    for v in TableauVisualization.objects.all().filter(project=domain):
        visualization_class = _make_visualization_class(vis_num, v)
        if visualization_class is not None:
            result.append(visualization_class)
        vis_num += 1
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
