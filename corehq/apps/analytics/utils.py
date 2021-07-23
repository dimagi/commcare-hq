import math
import time
import requests
import logging

from django.conf import settings

from corehq.util.metrics import metrics_gauge
from corehq.apps.accounting.models import Subscription, BillingAccount
from corehq.apps.es.users import UserES
from corehq.apps.users.models import WebUser, CommCareUser

logger = logging.getLogger('analytics')

MAX_API_RETRIES = 5


def get_meta(request):
    return {
        'HTTP_X_FORWARDED_FOR': request.META.get('HTTP_X_FORWARDED_FOR'),
        'REMOTE_ADDR': request.META.get('REMOTE_ADDR'),
    }


def analytics_enabled_for_email(email_address):
    from corehq.apps.users.models import CouchUser
    user = CouchUser.get_by_username(email_address)
    return user.analytics_enabled if user else True


def is_email_blocked_from_hubspot(email_address):
    email_domain = email_address.split('@')[-1]
    return BillingAccount.objects.filter(
        is_active=True,
        block_email_domains_from_hubspot__contains=[email_domain],
    ).exists()


def is_domain_blocked_from_hubspot(domain):
    return Subscription.visible_objects.filter(
        is_active=True,
        subscriber__domain=domain,
        account__is_active=True,
        account__block_hubspot_data_for_all_users=True,
    ).exists()


def hubspot_enabled_for_user(user):
    """
    Check if a user (or account policy) has given permission for Hubspot
    analytics to be synced for a given user.
    :param user: CouchUser or WebUser
    :return: Boolean (True if hubspot is enabled/allowed)
    """
    if is_email_blocked_from_hubspot(user.username):
        return False
    if isinstance(user, WebUser):
        web_user = user
    else:
        web_user = WebUser.get_by_username(user.username)
    if web_user:
        for domain in web_user.get_domains():
            if is_domain_blocked_from_hubspot(domain):
                return False
    else:
        commcare_user = CommCareUser.get_by_username(user.username)
        if is_domain_blocked_from_hubspot(commcare_user.domain):
            return False
    return user.analytics_enabled


def hubspot_enabled_for_email(email_address):
    from corehq.apps.users.models import CouchUser
    user = CouchUser.get_by_username(email_address)
    return hubspot_enabled_for_user(user) if user else True


def get_blocked_hubspot_domains():
    """
    Get the list of domains / project spaces that have active subscriptions
    with accounts that have blocked hubspot data.
    :return: list
    """
    return list(Subscription.visible_objects.filter(
        account__block_hubspot_data_for_all_users=True,
        is_active=True,
        account__is_active=True,
    ).values_list('subscriber__domain', flat=True))


def get_blocked_hubspot_email_domains():
    """
    Get the list of email domains (everything after the @ in an email address)
    that have been blocked from Hubspot by BillingAccounts (excluding gmail.com)
    :return: list
    """
    email_domains = {_email for email_list in BillingAccount.objects.filter(
        is_active=True,
    ).exclude(
        block_email_domains_from_hubspot=[],
    ).values_list(
        'block_email_domains_from_hubspot',
        flat=True,
    ) for _email in email_list}
    # we want to ensure that gmail.com is never a part of this list
    email_domains.difference_update(['gmail.com'])
    return list(email_domains)


def get_blocked_hubspot_accounts():
    return [
        f'{account[1]} - ID # {account[0]}'
        for account in BillingAccount.objects.filter(
            block_hubspot_data_for_all_users=True,
            is_active=True,
        ).values_list('id', 'name')
    ]


def get_instance_string():
    instance = settings.ANALYTICS_CONFIG.get('HQ_INSTANCE', '')
    env = '' if instance == 'www' else instance + '_'
    return env


def _delete_hubspot_contact(vid, retry_num=0):
    """
    Permanently deletes a Hubspot contact.
    :param vid:  (the contact ID)
    :param retry_num: the number of the current retry attempt
    :return: boolean if contact was deleted
    """
    if retry_num > 0:
        time.sleep(10)  # wait 10 seconds if this is another retry attempt

    api_key = settings.ANALYTICS_IDS.get('HUBSPOT_API_KEY', None)
    if api_key:
        try:
            req = requests.delete(
                f'https://api.hubapi.com/contacts/v1/contact/vid/{vid}',
                params={
                    'hapikey': api_key,
                }
            )
            if req.status_code == 404:
                return False
            req.raise_for_status()
        except (ConnectionError, requests.exceptions.HTTPError) as e:
            metrics_gauge(
                'commcare.hubspot_data.retry.delete_hubspot_contact',
                1
            )
            if retry_num <= MAX_API_RETRIES:
                return _delete_hubspot_contact(vid, retry_num + 1)
            else:
                logger.error(f"Failed to delete Hubspot contact {vid} due to "
                             f"{str(e)}.")
        else:
            return True
    return False


def _get_contact_ids_for_emails(list_of_emails, retry_num=0):
    """
    Gets a list of Contact IDs on Hubspot from a list of emails.
    If an email in the list doesn't exist on Hubspot, it's simply ignored.
    :param list_of_emails:
    :param retry_num: the number of the current retry attempt
    :return: list of contact ids
    """
    if retry_num > 0:
        time.sleep(10)  # wait 10 seconds if this is another retry attempt

    api_key = settings.ANALYTICS_IDS.get('HUBSPOT_API_KEY', None)
    if api_key:
        try:
            req = requests.get(
                "https://api.hubapi.com/contacts/v1/contact/emails/batch/",
                params={
                    'hapikey': api_key,
                    'email': list_of_emails,
                },
            )
            if req.status_code == 404:
                return []
            req.raise_for_status()
        except (ConnectionError, requests.exceptions.HTTPError) as e:
            metrics_gauge(
                'commcare.hubspot_data.retry.get_contact_ids_for_emails',
                1
            )
            if retry_num <= MAX_API_RETRIES:
                return _get_contact_ids_for_emails(list_of_emails, retry_num + 1)
            else:
                logger.error(f"Failed to get Hubspot contact ids for emails "
                             f"{list_of_emails.join(', ')} due to {str(e)}.")
        else:
            return req.json().keys()
    return []


def _get_contact_ids_for_email_domain(email_domain, retry_num=0):
    """
    Searches Hubspot for an email domain and returns the list of matching
    contact IDs for that email domain.
    :param email_domain:
    :param retry_num: the number of the current retry attempt
    :return: list of matching contact IDs
    """
    if retry_num > 0:
        time.sleep(10)  # wait 10 seconds if this is another retry attempt

    api_key = settings.ANALYTICS_IDS.get('HUBSPOT_API_KEY', None)
    if api_key:
        try:
            req = requests.get(
                "https://api.hubapi.com/contacts/v1/search/query",
                params={
                    'hapikey': api_key,
                    'q': f'@{email_domain}',
                },
            )
            if req.status_code == 404:
                return []
            req.raise_for_status()
        except (ConnectionError, requests.exceptions.HTTPError) as e:
            metrics_gauge(
                'commcare.hubspot_data.retry.get_contact_ids_for_email_domain',
                1
            )
            if retry_num <= MAX_API_RETRIES:
                return _get_contact_ids_for_email_domain(email_domain, retry_num + 1)
            else:
                logger.error(f"Failed to get Hubspot contact ids for email "
                             f"domain {email_domain} due to {str(e)}.")
        else:
            return [contact.get('vid') for contact in req.json().get('contacts')]
    return []


def remove_blocked_email_domains_from_hubspot(stdout=None):
    """
    Removes contacts from Hubspot that emails matching our list of
    blocked email domains.
    :param stdout: the stdout of a management command (if applicable)
    """
    blocked_email_domains = get_blocked_hubspot_email_domains()
    for email_domain in blocked_email_domains:
        ids_to_delete = _get_contact_ids_for_email_domain(email_domain)
        if stdout:
            stdout.write(f"\n\nChecking EMAIL DOMAIN {email_domain}")
            stdout.write(f"Found {len(ids_to_delete)} id(s) to delete.")
        num_deleted = sum(_delete_hubspot_contact(vid) for vid in ids_to_delete)
        metrics_gauge(
            'commcare.hubspot_data.deleted_user.blocked_email_domain',
            num_deleted,
            tags={
                'email_domain': email_domain,
                'ids_deleted': ids_to_delete,
            }
        )


def remove_blocked_domain_contacts_from_hubspot(stdout=None):
    """
    Removes contacts from Hubspot that are members of blocked domains.
    :param stdout: the stdout of a management command (if applicable)
    """
    blocked_domains = get_blocked_hubspot_domains()
    for domain in blocked_domains:
        if stdout:
            stdout.write(f"\n\nChecking DOMAIN {domain}...")
        user_query = UserES().domain(domain).source(['email', 'username'])

        total_users = user_query.count()
        chunk_size = 30  # Hubspot recommends fewer than 100 emails per request
        num_chunks = int(math.ceil(float(total_users) / float(chunk_size)))

        for chunk in range(num_chunks):
            blocked_users = (user_query
                             .size(chunk_size)
                             .start(chunk * chunk_size)
                             .run()
                             .hits)
            blocked_emails = []
            for user in blocked_users:
                username = user.get('username')
                user_email = user.get('email')
                blocked_emails.append(username)
                if user_email and user_email != username:
                    blocked_emails.append(user_email)
            ids_to_delete = _get_contact_ids_for_emails(set(blocked_emails))
            if stdout:
                stdout.write(f"Found {len(ids_to_delete)} id(s) to delete.")
            num_deleted = sum(_delete_hubspot_contact(vid) for vid in ids_to_delete)
            metrics_gauge(
                'commcare.hubspot_data.deleted_user.blocked_domain',
                num_deleted,
                tags={
                    'domain': domain,
                    'ids_deleted': ids_to_delete,
                }
            )


def is_hubspot_js_allowed_for_request(request):
    """
    This determines whether a particular request is allowed to load any
    Hubspot javascript, even when Hubspot analytics is supported by the
    environment. This is done to ensure that no accidental Hubspot popups and
    scripts are executed on projects that have explicitly asked to be excluded
    from Hubspot analytics.
    :param request: HttpRequest
    :return: boolean (True if Hubspot javascript is allowed)
    """
    if not settings.IS_SAAS_ENVIRONMENT:
        return False

    is_hubspot_js_allowed = True
    if hasattr(request, 'subscription'):
        try:
            account = request.subscription.account
            is_hubspot_js_allowed = not account.block_hubspot_data_for_all_users
        except BillingAccount.DoesNotExist:
            pass
    return is_hubspot_js_allowed
