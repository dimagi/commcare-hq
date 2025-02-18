from django_tables2 import tables

DEFAULT_HTMX_TEMPLATE = "hqwebapp/tables/bootstrap5_htmx.html"


class BaseHtmxTable(tables.Table):
    """
    This class provides a starting point for using HTMX with Django Tables.

    usage:

        class MyNewTable(BaseHtmxTable):

            class Meta(BaseHtmxTable.Meta):
                pass  # or you can override or add table attributes here -- see Django Tables docs

    Optional class properties:

        :container_id: -  a string
            The `container_id` is used as the css `id` of the parent div surrounding table,
            its pagination, and related elements.

            You can then use `hq-hx-refresh="#{{ container_id }}"` to trigger a
            refresh on the table from another HTMX request on the page.

            When not specified, `container_id` is the table's class name

        :loading_indicator_id: - a string
            By default this is ":container_id:-loading". It is the css id of the table's
            loading indicator that covers the whole table. The loading indicator for the table
            can be triggered by any element making an HTMX request using
            `hq-hx-loading="{{ loading_indicator_id }}"`.

    See `hqwebapp/tables/bootstrap5_htmx.html` and `hqwebapp/tables/bootstrap5.html` for usage of the
    above properties and related `hq-hx-` attributes. There is also an example in the styleguide.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not hasattr(self, 'container_id'):
            self.container_id = self.__class__.__name__
        if not hasattr(self, 'loading_indicator_id'):
            self.loading_indicator_id = f"{self.container_id}-loading"

    class Meta:
        attrs = {
            'class': 'table table-striped',
        }
        template_name = DEFAULT_HTMX_TEMPLATE
