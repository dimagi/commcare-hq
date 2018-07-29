from __future__ import absolute_import
from __future__ import unicode_literals
import six.moves.urllib.parse
from collections import namedtuple

from django.urls import reverse
from django.utils.translation import ugettext as _


def dropdown_dict(title, url=None, html=None,
                  is_header=False, is_divider=False, data_id=None,
                  second_level_dropdowns=[]):
    if second_level_dropdowns:
        return submenu_dropdown_dict(title, url, second_level_dropdowns)
    else:
        return main_menu_dropdown_dict(title, url=url, html=html,
                                       is_header=is_header,
                                       is_divider=is_divider,
                                       data_id=data_id,)


def sidebar_to_dropdown(sidebar_items, domain=None, current_url=None):
    """
    Formats sidebar_items as dropdown items
    Sample input:
        [(u'Application Users',
          [{'description': u'Create and manage users for CommCare and CloudCare.',
            'show_in_dropdown': True,
            'subpages': [{'title': <function commcare_username at 0x109869488>,
                          'urlname': 'edit_commcare_user'},
                         {'title': u'Bulk Upload',
                          'urlname': 'upload_commcare_users'},
                         {'title': 'Confirm Billing Information',],
            'title': u'Mobile Workers',
            'url': '/a/sravan-test/settings/users/commcare/'},
         (u'Project Users',
          [{'description': u'Grant other CommCare HQ users access
                            to your project and manage user roles.',
            'show_in_dropdown': True,
            'subpages': [{'title': u'Add Web User',
                          'urlname': 'invite_web_user'},
                         {'title': <function web_username at 0x10982a9b0>,
                          'urlname': 'user_account'},
                         {'title': u'My Information',
                          'urlname': 'domain_my_account'}],
            'title': <django.utils.functional.__proxy__ object at 0x106a5c790>,
            'url': '/a/sravan-test/settings/users/web/'}])]
    Sample output:
        [{'data_id': None,
          'html': None,
          'is_divider': False,
          'is_header': True,
          'title': u'Application Users',
          'url': None},
         {'data_id': None,
          'html': None,
          'is_divider': False,
          'is_header': False,
          'title': u'Mobile Workers',
          'url': '/a/sravan-test/settings/users/commcare/'},
         {'data_id': None,
          'html': None,
          'is_divider': False,
          'is_header': False,
          'title': u'Groups',
          'url': '/a/sravan-test/settings/users/groups/'},
         {'data_id': None,
          'html': None,
          'is_divider': False,
          'is_header': True,
          'title': u'Project Users',
          'url': None},]
    """
    dropdown_items = []
    more_items_in_sidebar = False
    for side_header, side_list in sidebar_items:
        dropdown_header = dropdown_dict(side_header, is_header=True)
        current_dropdown_items = []
        for side_item in side_list:
            show_in_dropdown = side_item.get("show_in_dropdown", False)
            if show_in_dropdown:
                second_level_dropdowns = subpages_as_dropdowns(
                    side_item.get('subpages', []), level=2, domain=domain)
                dropdown_item = dropdown_dict(
                    side_item['title'],
                    url=side_item['url'],
                    second_level_dropdowns=second_level_dropdowns,
                )
                current_dropdown_items.append(dropdown_item)
                first_level_dropdowns = subpages_as_dropdowns(
                    side_item.get('subpages', []), level=1, domain=domain
                )
                current_dropdown_items = current_dropdown_items + first_level_dropdowns
            else:
                more_items_in_sidebar = True
        if current_dropdown_items:
            dropdown_items.extend([dropdown_header] + current_dropdown_items)

    if dropdown_items and more_items_in_sidebar and current_url:
        return dropdown_items + divider_and_more_menu(current_url)
    else:
        return dropdown_items


def submenu_dropdown_dict(title, url, menu):
    return {
        'title': title,
        'url': url,
        'is_second_level': True,
        'submenu': menu,
    }


def divider_and_more_menu(url):
    return [dropdown_dict('placeholder', is_divider=True),
            dropdown_dict(_('View All'), url=url)]


def main_menu_dropdown_dict(title, url=None, html=None,
                            is_header=False, is_divider=False, data_id=None,
                            second_level_dropdowns=[]):
    return {
        'title': title,
        'url': url,
        'html': html,
        'is_header': is_header,
        'is_divider': is_divider,
        'data_id': data_id,
    }


def subpages_as_dropdowns(subpages, level, domain=None):
    """
        formats subpages of a sidebar_item as 1st or 2nd level dropdown items
        depending on if level is 1 or 2 respectively
    """
    def is_dropdown(subpage):
        if subpage.get('show_in_dropdown', False) and level == 1:
            return subpage.get('show_in_first_level', False)
        elif subpage.get('show_in_dropdown', False) and level == 2:
            return not subpage.get('show_in_first_level', False)

    return [dropdown_dict(
            subpage['title'],
            url=reverse(subpage['urlname'], args=[domain]))
            for subpage in subpages if is_dropdown(subpage)]


def path_starts_with_url(path, url):
    """
    >>> path_starts_with_url('/a/test/reports/saved/', 'https://www.commcarehq.org/a/test/reports/')
    True
    >>> path_starts_with_url('/a/test/reports/saved/', '/a/test/reports/')
    True
    >>> path_starts_with_url('/a/test/reports/', '/a/test/reports/saved/')
    False
    """
    url = six.moves.urllib.parse.urlparse(url).path
    return path.startswith(url)


SidebarPosition = namedtuple("SidebarPosition", ["heading", "index"])


def regroup_sidebar_items(ordering, sidebar_items):
    reports_to_move = {}  # report class name to SidebarPosition mapping
    for heading, reports in ordering:
        for i, report_class_name in enumerate(reports):
            reports_to_move[report_class_name] = SidebarPosition(heading, i)

    # A mapping of headings to lists of 2-tuples. The tuples are index (under the heading) and the item itself.
    new_sections = {heading: [] for heading, _ in ordering}
    # A mapping of headings to lists of sidebar items.
    old_sections = {heading: [] for heading, _ in sidebar_items}

    # extract the sidebar items that to their new heading sections (or their old sections)
    for heading, items in sidebar_items:
        for item in items:
            new_position = reports_to_move.get(item['class_name'], None)
            if new_position:
                new_sections[new_position.heading].append((new_position.index, item))
            else:
                old_sections[heading].append(item)

    # Flatten the intermediary data structures
    flat_new_sections = [
        (heading, [item for index, item in sorted(new_sections[heading])])
        for heading, _ in ordering
    ]
    flat_old_sections = [(heading, old_sections[heading]) for heading, _ in sidebar_items]
    return flat_new_sections + flat_old_sections
