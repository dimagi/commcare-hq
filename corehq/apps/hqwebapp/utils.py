import logging

from django.core.urlresolvers import reverse
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.translation import ugettext as _

from Crypto.PublicKey import RSA
from Crypto.Hash import SHA256
from Crypto.Signature import PKCS1_PSS

from dimagi.utils.decorators.memoized import memoized

from corehq.apps.hqwebapp.forms import BulkUploadForm
from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.apps.users.models import WebUser


logger = logging.getLogger(__name__)


@memoized
def get_hq_private_key():
    if settings.HQ_PRIVATE_KEY:
        return RSA.importKey(settings.HQ_PRIVATE_KEY)

    raise Exception('No private key found in localsettings.HQ_PRIVATE_KEY')


def sign(message):
    """
    Signs the SHA256 hash of message with HQ's private key, and returns
    the binary signature. The scheme used is RSASSA-PSS.
    """
    private_key = get_hq_private_key()
    sha256_hash = SHA256.new(message)
    signature = PKCS1_PSS.new(private_key).sign(sha256_hash)
    return signature


def send_confirmation_email(invitation):
    invited_user = invitation.email
    subject = '%s accepted your invitation to CommCare HQ' % invited_user
    recipient = WebUser.get_by_user_id(invitation.invited_by).get_email()
    context = {
        'invited_user': invited_user,
    }
    html_content = render_to_string('domain/email/invite_confirmation.html',
                                    context)
    text_content = render_to_string('domain/email/invite_confirmation.txt',
                                    context)
    send_html_email_async.delay(subject, recipient, html_content,
                                text_content=text_content)


def get_bulk_upload_form(context, context_key="bulk_upload"):
    return BulkUploadForm(
        context[context_key]['plural_noun'],
        context[context_key].get('action'),
        context_key + "_form"
    )


def sidebar_to_dropdown(sidebar_items, domain=None, current_url_name=None):
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

    if more_items_in_sidebar and current_url_name:
        return dropdown_items + divider_and_more_menu(current_url_name)
    else:
        return dropdown_items


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


def csrf_inline(request):
    """
    Returns "<input type='hidden' name='csrfmiddlewaretoken' value='<csrf-token-value>' />",
    same as csrf_token template tag, but a shortcut without needing a Template or Context explicitly.

    Useful for adding inline forms in messages for e.g. while showing an "'undo' Archive Form" message
    """
    from django.template import Template, RequestContext
    node = "{% csrf_token %}"
    return Template(node).render(RequestContext(request))
