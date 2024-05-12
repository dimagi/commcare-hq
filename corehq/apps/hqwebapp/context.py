from collections import namedtuple

Section = namedtuple('Section', 'page_name url')
ParentPage = namedtuple('ParentPage', 'title url')


def get_page_context(page_title, page_url, page_name=None, parent_pages=None, domain=None, section=None):
    """This sets up the page context for functional views inheriting from the following base templates:
    hqwebapp/{bootstrap_version}/base_page.html
    hqwebapp/{bootstrap_version}/base_section.html
        note: do not inherit from two_column.html, unless you have a very specific use-case
        for navigation, see the style guide section on Navigation

    :param page_title: an instance of ``str``, title of the page...inserted into <title></title> tags
    :param page_url: an instance of ``str``, often reverse("urlname") or reverse("urlname", args=[...])
    :param page_name: an instance of ``str``, human-visible page name, defaults to page_title
    :param parent_pages: ``None`` or a ``list`` of ``ParentPage``
    :param domain: an instance of ``str``, the domain slug
    :param section: an instance of the ``Section`` context
    """
    page_name = page_name or page_title
    parent_pages = parent_pages or []
    base_context = {
        'current_page': {
            'page_name': page_name,
            'title': page_title,
            'url': page_url,
            'parents': parent_pages,
        },
    }
    if domain:
        base_context['domain'] = domain
    if section:
        base_context['section'] = section
    return base_context
