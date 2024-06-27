from django.template import Context, Template
from django.template.loader import get_template

from django_tables2 import columns


class EditableColumn(columns.TemplateColumn):

    def __init__(self, *args, **kwargs):
        super().__init__(
            template_name="prototype/data_cleaning/partials/columns/editable_column.html",
            *args, **kwargs
        )

    @staticmethod
    def get_edited_slug(slug):
        return f"{slug}__edited"

    def render(self, record, table, value, bound_column, **kwargs):
        # Taken from the original TemplateColumn.render, adding direct context for the edited value
        context = getattr(table, "context", Context())
        edited_accessor = self.get_edited_slug(bound_column.accessor)
        additional_context = {
            "table": table,
            "default": bound_column.default,
            "column": bound_column,
            "record": record,
            "value": value,
            "edited_value": record.get(edited_accessor),
            "row_counter": kwargs["bound_row"].row_counter,
        }
        additional_context.update(self.extra_context)
        with context.update(additional_context):
            if self.template_code:
                return Template(self.template_code).render(context)
            else:
                return get_template(self.template_name).render(context.flatten())
