from django.utils.translation import gettext_lazy
from django_tables2 import columns

from corehq.apps.hqwebapp.tables.htmx import BaseHtmxTable


class ExampleFakeDataTable(BaseHtmxTable):
    """
    This defines the columns for the table rendered by `ExamplePaginatedTableView`.

    The variable names for each column match the keys available in
    `generate_example_pagination_data` below, and the `verbose_name` specifies
    the name shown to the user.

    We are using the `BaseHtmxTable` parent class and defining its Meta class
    below based on `BaseHtmxTable.Meta`, as it provides some shortcuts
    and default styling for our use of django-tables2 with HTMX.
    """
    class Meta(BaseHtmxTable.Meta):
        pass

    name = columns.Column(
        verbose_name=gettext_lazy("Name"),
    )
    color = columns.Column(
        verbose_name=gettext_lazy("Color"),
    )
    big_cat = columns.Column(
        verbose_name=gettext_lazy("Big Cats"),
    )
    dob = columns.Column(
        verbose_name=gettext_lazy("Date of Birth"),
    )
    app = columns.Column(
        verbose_name=gettext_lazy("Application"),
    )
    date_opened = columns.Column(
        verbose_name=gettext_lazy("Opened On"),
    )
    owner = columns.Column(
        verbose_name=gettext_lazy("Owner"),
    )
    status = columns.Column(
        verbose_name=gettext_lazy("Status"),
    )
