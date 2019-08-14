# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _
from django.views.decorators.http import require_GET, require_POST

from corehq import toggles
from corehq.apps.case_templates.models import CaseTemplate
from corehq.apps.data_interfaces.views import DataInterfaceSection
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions


@require_POST
@login_and_domain_required
@require_permission(Permissions.edit_data)
@toggles.CASE_TEMPLATES.required_decorator()
def create_template_view(request, domain):
    name = request.POST.get('name')
    comment = request.POST.get('comment') or None
    root_case_id = request.POST.get('case_id')
    user_id = request.couch_user.user_id

    try:
        template = CaseTemplate.create(domain, root_case_id, name, user_id, comment)
    except Exception:
        messages.error(request, _("Something went wrong"))
    else:
        messages.success(
            request,
            _('New template with name: "{template_name}" successfully created').format(
                template_name=template.name)
        )

    return HttpResponseRedirect(reverse(CaseTemplatesListView.urlname, args=[domain]))


class CaseTemplatesListView(DataInterfaceSection):
    urlname = 'case_templates_list'
    page_title = _("Manage Case Templates")

    template_name = 'case_templates/case_templates_list.html'

    @method_decorator(toggles.CASE_TEMPLATES.required_decorator())
    @method_decorator(require_permission(Permissions.edit_data))
    def dispatch(self, request, *args, **kwargs):
        return super(CaseTemplatesListView, self).dispatch(request, *args, **kwargs)

    @property
    def page_context(self):
        return {
            'case_templates': CaseTemplate.objects.filter(domain=self.domain).all(),
        }


@require_POST
@login_and_domain_required
@require_permission(Permissions.edit_data)
@toggles.CASE_TEMPLATES.required_decorator()
def create_instance_view(request, domain):
    template_id = request.POST.get('template_id')

    template = CaseTemplate.objects.get(domain=domain, template_id=template_id)
    new_root_id = template.create_instance()

    created_case_ids = template.instance_cases.filter(ancestor_id=new_root_id).values_list('case_id', flat=True)
    search_string = " ".join("_id:{}".format(case_id) for case_id in created_case_ids)
    search_url = "{url}?search_query={query}".format(
        url=reverse('project_report_dispatcher', args=[domain, 'case_list']),
        query=search_string
    )

    messages.success(request, _("Successfully created {} cases").format(len(created_case_ids)))

    return HttpResponseRedirect(search_url)


@require_POST
@login_and_domain_required
@require_permission(Permissions.edit_data)
@toggles.CASE_TEMPLATES.required_decorator()
def delete_template_view(request, domain):
    template_id = request.POST.get('template_id')

    template = CaseTemplate.objects.get(domain=domain, template_id=template_id)
    template.delete()

    messages.success(request, _("Template successfully deleted"))

    return HttpResponseRedirect(reverse(CaseTemplatesListView.urlname, args=[domain]))
