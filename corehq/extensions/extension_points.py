from corehq.extensions import register_extension_point
from corehq.extensions.interface import ExtensionPoint

register_extension_point(ExtensionPoint(
    "uitab:dropdown_items", providing_args=("tab", "domain", "request"),
    docs="""
        Called by UI tabs during rendering. Receivers must return a dict with keys:
        * title
        * url (default=None)
        * html (default=None)
        * is_header (default=False)
        * is_divider (default=False)
        * data_id (default=None)
    """
))


register_extension_point(ExtensionPoint(
    "urls:domain_specific", providing_args=(),
    docs="""
        Return a list of URL module strings to be included in the domain specific
        URL patterns.
    """
))
