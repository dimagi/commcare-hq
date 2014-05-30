# coding=utf-8
import functools
from pydoc import html
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from corehq.apps.receiverwrapper.util import get_meta_appversion_text, get_build_version, \
    BuildVersionSource
from couchdbkit import ResourceNotFound
from corehq.apps.app_manager.models import get_app
from corehq.apps.reports import util
from corehq.apps.reports.filters.select import SelectApplicationFilter
from corehq.apps.reports.standard import ProjectReportParametersMixin, ProjectReport
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DTSortType
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.util import make_form_couch_key
from couchforms.models import XFormInstance
from django.utils.translation import ugettext_noop
from django.utils.translation import ugettext as _


class DeploymentsReport(GenericTabularReport, ProjectReport, ProjectReportParametersMixin):
    """
        Base class for all deployments reports
    """
   
    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        # for commtrack/connect projects - only show if the user can view apps
        if project.commtrack_enabled or project.commconnect_enabled:
            return user and (user.is_superuser or user.has_permission(domain, 'edit_apps'))
        return super(DeploymentsReport, cls).show_in_navigation(domain, project, user)


def _build_html(version, version_source):
    version = version or _("Unknown")

    def fmt(title, extra_class=u'', extra_text=u''):
        return format_html(
            u'<span class="label{extra_class}" title="{title}">'
            u'{extra_text}{version}</span>',
            version=version,
            title=title,
            extra_class=extra_class,
            extra_text=extra_text,
        )
    if version_source == BuildVersionSource.BUILD_ID:
        return fmt(title=_("This was taken from build id"),
                   extra_class=u' label-success')
    elif version_source == BuildVersionSource.APPVERSION_TEXT:
        return fmt(title=_("This was taken from appversion text"))
    elif version_source == BuildVersionSource.XFORM_VERSION:
        return fmt(title=_("This was taken from xform version"),
                   extra_text=u'≥ ')
    elif version_source == BuildVersionSource.NONE:
        return fmt(title=_("Unable to determine the build version"))
    else:
        raise AssertionError('version_source must be '
                             'a BuildVersionSource constant')


class ApplicationStatusReport(DeploymentsReport):
    name = ugettext_noop("Application Status")
    slug = "app_status"
    fields = ['corehq.apps.reports.filters.users.UserTypeFilter',
              'corehq.apps.reports.filters.select.GroupFilter',
              'corehq.apps.reports.filters.select.SelectApplicationFilter']

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(_("Username")),
            DataTablesColumn(_("Last Seen (UTC)"),
                             sort_type=DTSortType.NUMERIC),
            DataTablesColumn(_("Application (Deployed Build)"))
        )

    @property
    def rows(self):
        rows = []
        selected_app = self.request_params.get(SelectApplicationFilter.slug, '')

        for user in self.users:
            last_seen = self.table_cell(-1, _("Never"))
            app_name = None

            key = make_form_couch_key(self.domain, user_id=user.user_id,
                                      app_id=selected_app or None)
            xform = XFormInstance.view(
                "reports_forms/all_forms",
                startkey=key+[{}],
                endkey=key,
                include_docs=True,
                descending=True,
                reduce=False,
                limit=1,
            ).first()

            if xform:
                last_seen = util.format_relative_date(xform.received_on)
                build_version, build_version_source = get_build_version(xform)

                if xform.app_id:
                    try:
                        app = get_app(self.domain, xform.app_id)
                    except ResourceNotFound:
                        pass
                    else:
                        app_name = app.name
                else:
                    app_name = get_meta_appversion_text(xform)

                build_html = _build_html(build_version, build_version_source)
                app_name = app_name or _("Unknown App")
                app_name = format_html(
                    u'{} {}', app_name, mark_safe(build_html),
                )

            if app_name is None and selected_app:
                continue

            rows.append(
                [user.username_in_report, last_seen, app_name or "---"]
            )
        return rows
