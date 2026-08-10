from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from django_tables2 import columns, tables

from corehq.apps.hqwebapp.tables.htmx import BaseHtmxTable


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
    delivery = columns.Column(
        verbose_name=_("Delivery"),
    )
    public_url = columns.Column(
        verbose_name=_("Public URL"),
    )
    actions = columns.Column(
        verbose_name=_("Actions"),
    )

    def __init__(self, timezone, **kwargs):
        super().__init__(**kwargs)
        self.timezone = timezone

    def render_label(self, value):
        return format_html('<div class="fw-semibold">{}</div>', value)
