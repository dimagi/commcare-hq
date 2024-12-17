from django import template

register = template.Library()


@register.inclusion_tag('hqwebapp/tables/header.html', takes_context=True)
def render_header(context, link_type=None):
    """
    Based on
    https://stackoverflow.com/questions/31838533/django-table2-multi-column-sorting-ui/31865765#31865765
    For allowing multiple column sorting
    """
    context['use_htmx_links'] = link_type == 'htmx'
    sorted_columns = context['request'].GET.getlist('sort')
    for column in context['table'].columns:
        column.sort_desc = f"-{column.name}" in sorted_columns
    return context
