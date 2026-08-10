from django.template.loader import render_to_string
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from django_tables2 import columns, tables
from memoized import memoized

from corehq.apps.hqwebapp.tables.htmx import BaseHtmxTable
from corehq.apps.public_webforms.form_paths import (
    get_public_webform_form_paths,
)
from corehq.apps.public_webforms.models import (
    PublicWebformStatus,
    PublicWebformType,
)
from corehq.util.timezones.conversions import ServerTime

STATUS_BADGES = {
    PublicWebformStatus.OPEN:
        'bg-success-subtle border border-success text-success-emphasis',
    PublicWebformStatus.CLOSED:
        'bg-secondary-subtle border border-secondary text-secondary-emphasis',
    PublicWebformStatus.EXPIRED:
        'bg-warning-subtle border border-warning text-warning-emphasis',
}
TYPE_BADGES = {
    PublicWebformType.REGISTRATION: 'bg-primary-subtle text-primary-emphasis',
    PublicWebformType.SURVEY: 'bg-info-subtle text-info-emphasis',
}


class PublicWebformTable(BaseHtmxTable, tables.Table):
    """The dashboard's list of a project's public webforms."""

    class Meta(BaseHtmxTable.Meta):
        template_name = 'public_webforms/tables/public_webform.html'
        attrs = {
            'class': 'table table-hover px-2',
            'thead': {'class': 'table-light text-uppercase'},
        }
        row_attrs = {
            'class': 'align-middle',
        }
        orderable = False

    label = columns.Column(
        verbose_name=_("Form"),
    )
    session_type = columns.Column(
        verbose_name=_("Type"),
    )
    status = columns.Column(
        verbose_name=_("Status"),
    )
    submissions = columns.Column(
        verbose_name=_("Submissions"),
    )
    expires_at = columns.Column(
        verbose_name=_("Closes"),
    )
    delivery = columns.TemplateColumn(
        template_name='public_webforms/columns/delivery.html',
        verbose_name=_("Delivery"),
        attrs={'td': {'class': 'text-nowrap'}},
        # nothing on the record to accessor, so render unconditionally
        empty_values=(),
    )
    public_url = columns.TemplateColumn(
        template_name='public_webforms/columns/public_url.html',
        verbose_name=_("Public URL"),
    )
    actions = columns.TemplateColumn(
        template_name='public_webforms/columns/actions.html',
        verbose_name=_("Actions"),
        attrs={'td': {'class': 'text-nowrap'}},
        empty_values=(),
    )

    def __init__(self, domain, timezone, is_filtered=False, **kwargs):
        super().__init__(**kwargs)
        self.domain = domain
        self.timezone = timezone
        self.is_filtered = is_filtered

    @property
    @memoized
    def form_paths(self):
        return get_public_webform_form_paths(
            self.domain, [row.record for row in self.paginated_rows])

    def render_label(self, record, value):
        return render_to_string('public_webforms/columns/form.html', {
            'label': value,
            'path': self.form_paths[record.id],
        })

    def render_session_type(self, record):
        session_type = PublicWebformType(record.session_type)
        return format_html(
            '<span class="badge fs-6 {}">{}</span>',
            TYPE_BADGES[session_type],
            session_type.label,
        )

    def render_status(self, value):
        status = PublicWebformStatus(value)
        return format_html(
            '<span class="badge fs-6 text-center rounded-pill {}">{}</span>',
            STATUS_BADGES[status],
            status.label,
        )

    def render_expires_at(self, value):
        return ServerTime(value).user_time(self.timezone).ui_string()
