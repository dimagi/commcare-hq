import inspect

from corehq.plugins import register_extension_point
from corehq.plugins.interface import ExtensionPoint

register_extension_point(ExtensionPoint(
    "uitab:dropdown_items", providing_args=("tab", "domain", "request"),
    docs=inspect.cleandoc("""
        Called by UI tabs during rendering. Receivers must return a dict with keys:
        * title
        * url (default=None)
        * html (default=None)
        * is_header (default=False)
        * is_divider (default=False)
        * data_id (default=None)
    """)
))
