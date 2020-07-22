from corehq.extensions.interface import extension_point


@extension_point
def domain_specific_urls():
    """Return a list of URL module strings to be included in the domain specific URL patterns."""


@extension_point
def uitab_dropdown_items(tab, domain, request):
    """Called by UI tabs during rendering.

    :returns: Dict with keys:
        * title
        * url (default=None)
        * html (default=None)
        * is_header (default=False)
        * is_divider (default=False)
        * data_id (default=None)
    """
