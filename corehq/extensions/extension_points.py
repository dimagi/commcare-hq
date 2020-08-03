from typing import List, Dict

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
def uitab_dropdown_items(tab, domain, request) -> List[Dict]:
    """Add dropdown items to UI Tabs.

    Parameters:
        :param tab: Name of the tab that items will be added to
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
