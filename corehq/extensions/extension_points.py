from typing import List, Dict, Tuple

from corehq.extensions import extension_point, ResultFormat


@extension_point(result_format=ResultFormat.FLATTEN)
def domain_specific_urls() -> List[str]:
    """Add domain specific URLs to the Django URLs module.

    Parameters:
        None

    Returns:
        A list of URL module strings
    """


@extension_point(result_format=ResultFormat.FLATTEN)
def uitab_dropdown_items(tab_name, tab, domain, request) -> List[Dict]:
    """Add dropdown items to UI Tabs.

    Parameters:
        :param tab_name: Name of the tab that items will be added to
        :param tab: The tab instance
        :param domain: The domain of the current request
        :param request: The current request

    Returns:
        A dict with the following keys:

        * title
        * url (default=None)
        * html (default=None)
        * is_header (default=False)
        * is_divider (default=False)
        * data_id (default=None)
    """


@extension_point(result_format=ResultFormat.FLATTEN)
def uitab_sidebar_items(tab_name, tab, domain, request) -> List[Tuple[str, List[dict]]]:
    """Add sidebar items to UI tabs.

    Parameters:
        :param tab_name: Name of the UI Tab
        :param tab: The tab instance
        :param domain: The domain name
        :param request: The request object

    Returns:
       A list of tuples: Tuple[header_text, List[dict]]. The dictionaries must have
       the following keys:

       * title: Link text
       * url: relative URL for the UI
       * icon: Link icon
       * show_in_dropdown (optional): boolean
    """
