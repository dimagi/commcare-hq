import math
import time
import requests
import logging

from django.conf import settings

from corehq.util.metrics import metrics_counter
from corehq.apps.accounting.models import Subscription, BillingAccount
from corehq.apps.es.users import UserES
from corehq.apps.users.models import WebUser, CommCareUser, Invitation

logger = logging.getLogger('analytics')

MAX_API_RETRIES = 5

ALLOWED_CONVERSIONS = [
    'Blog',
    'Case study/ Ev. Base',
    'Contact us',
    'Event',
    'Live Chat',
    'Newletter',
    'Newsletter',
    'Offer',
    'Outbound',
    'Paid Ads',
    'Video',
]


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
    if isinstance(user, WebUser):
        web_user = user
    else:
        web_user = WebUser.get_by_username(user.username)
    if web_user:
        for domain in web_user.get_domains():
            if is_domain_blocked_from_hubspot(domain):
                return False
        if has_user_accepted_invitation_to_blocked_hubspot_domain(web_user):
            return False
    else:
        commcare_user = CommCareUser.get_by_username(user.username)
        if is_domain_blocked_from_hubspot(commcare_user.domain):
            return False
    return user.analytics_enabled


def has_user_accepted_invitation_to_blocked_hubspot_domain(web_user):
    blocked_domains = get_blocked_hubspot_domains()
    return Invitation.objects.filter(
        domain__in=blocked_domains,
        is_accepted=True,
        email=web_user.username
    ).exists()


def emails_that_accepted_invitations_to_blocked_hubspot_domains():
    blocked_domains = get_blocked_hubspot_domains()
    return Invitation.objects.filter(
        domain__in=blocked_domains,
        is_accepted=True,
    ).values_list('email', flat=True)


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


def get_blocked_hubspot_accounts():
    return [
        f'{account[1]} - ID # {account[0]}'
        for account in BillingAccount.objects.filter(
            block_hubspot_data_for_all_users=True,
            is_active=True,
        ).values_list('id', 'name')
    ]





def _delete_hubspot_contact(vid, retry_num=0):
    """
    Permanently deletes a Hubspot contact.
    :param vid:  (the contact ID)
    :param retry_num: the number of the current retry attempt
    :return: boolean if contact was deleted
    """
    if retry_num > 0:
        time.sleep(10)  # wait 10 seconds if this is another retry attempt

    access_token = settings.ANALYTICS_IDS.get('HUBSPOT_ACCESS_TOKEN', None)
    if access_token:
        try:
            req = requests.delete(
                f'https://api.hubapi.com/contacts/v1/contact/vid/{vid}',
                headers={
                    'authorization': 'Bearer %s' % access_token,
                }
            )
            if req.status_code == 404:
                return False
            req.raise_for_status()
        except (ConnectionError, requests.exceptions.HTTPError) as e:
            metrics_counter(
                'commcare.hubspot_data.retry.delete_hubspot_contact'
            )
            if retry_num <= MAX_API_RETRIES:
                return _delete_hubspot_contact(vid, retry_num + 1)
            else:
                metrics_counter(
                    'commcare.hubspot_data.error.delete_hubspot_contact',
                    tags={
                        'error': str(e),
                    }
                )
        else:
            return True
    return False


def _get_contacts_from_hubspot(list_of_emails, retry_num=0, record_metrics=True):
    """
    Gets a list of Contacts on Hubspot from a list of emails.
    If an email in the list doesn't exist on Hubspot, it's simply ignored.
    :param list_of_emails:
    :param retry_num: the number of the current retry attempt
    :param record_metrics: whether metrics should be sent to datadog
    :return: HubSpot contacts as dict
    """
    if retry_num > 0:
        time.sleep(10)  # wait 10 seconds if this is another retry attempt

    access_token = settings.ANALYTICS_IDS.get('HUBSPOT_ACCESS_TOKEN', None)
    if access_token:
        try:
            req = requests.get(
                "https://api.hubapi.com/contacts/v1/contact/emails/batch/",
                headers={
                    'authorization': 'Bearer %s' % access_token,
                },
                params={
                    'email': list_of_emails,
                },
            )
            if req.status_code == 404:
                return []
            req.raise_for_status()
        except (ConnectionError, requests.exceptions.HTTPError) as e:
            if record_metrics:
                metrics_counter(
                    'commcare.hubspot_data.retry.get_contact_ids_for_emails'
                )
            if retry_num <= MAX_API_RETRIES:
                return _get_contacts_from_hubspot(list_of_emails, retry_num + 1)
            elif record_metrics:
                metrics_counter(
                    'commcare.hubspot_data.error.get_contact_ids_for_emails',
                    tags={
                        'error': str(e),
                    }
                )
        else:
            return req.json()
    return {}


def get_first_conversion_status_for_emails(list_of_emails):
    """
    This returns the First Conversion (clustered) property for each contact in
    list_of_emails if that email is present in HubSpot
    :param list_of_emails:
    :return: list of contact ids
    """
    hubspot_contacts = _get_contacts_from_hubspot(
        list_of_emails, record_metrics=False
    )
    status_summary = {}
    for contact_id, data in hubspot_contacts.items():
        first_conversion_status = data.get(
            'properties', {}
        ).get('first_conversion_clustered_', {}).get('value')
        email = data.get(
            'properties', {}
        ).get('email', {}).get('value')
        if email:
            status_summary[email] = first_conversion_status
    return status_summary


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
            ids_to_delete = _get_contact_ids_to_delete(set(blocked_emails))
            if stdout:
                stdout.write(f"Found {len(ids_to_delete)} id(s) to delete.")
            num_deleted = sum(_delete_hubspot_contact(vid) for vid in ids_to_delete)
            metrics_counter(
                'commcare.hubspot_data.deleted_user.blocked_domain',
                num_deleted,
                tags={
                    'domain': domain,
                }
            )


def remove_blocked_domain_invited_users_from_hubspot(stdout=None):
    """
    Removes contacts from Hubspot who have ever accepted an invitation on HQ
    from a domain that is blocking Hubspot data.
    :param stdout: the stdout of a management command (if applicable)
    """
    blocked_user_emails = emails_that_accepted_invitations_to_blocked_hubspot_domains()
    total_users = blocked_user_emails.count()
    chunk_size = 30  # Hubspot recommends fewer than 100 emails per request
    num_chunks = int(math.ceil(float(total_users) / float(chunk_size)))

    if stdout:
        stdout.write("\n\nChecking Invited Users...")

    for chunk in range(num_chunks):
        start = chunk * chunk_size
        end = (chunk + 1) * chunk_size
        emails_to_check = blocked_user_emails[start:end]
        ids_to_delete = _get_contact_ids_to_delete(set(emails_to_check))
        if stdout:
            stdout.write(f"Found {len(ids_to_delete)} id(s) to delete.")
        num_deleted = sum(_delete_hubspot_contact(vid) for vid in ids_to_delete)
        metrics_counter(
            'commcare.hubspot_data.deleted_user.blocked_domain_invitation',
            num_deleted
        )


def _get_contact_ids_to_delete(list_of_emails):
    """
    Gets a list of Contact IDs be deleted from Hubspot based on the
    allowed First Conversion (clustered) property set on those contacts.
    :param list_of_emails:
    :return: list of contact ids
    """
    hubspot_contacts = _get_contacts_from_hubspot(list_of_emails)
    ids_to_delete = []
    for contact_id, data in hubspot_contacts.items():
        first_conversion_status = data.get(
            'properties', {}
        ).get('first_conversion_clustered_', {}).get('value')

        # If a user's first conversion IS in the allowed list, it means
        # they have directly interacted with us and we want to keep them
        # in the email list. However, we will not send project data
        # about them to HubSpot as they will still be blocked from
        # updates in track_periodic_data.
        if first_conversion_status not in ALLOWED_CONVERSIONS:
            ids_to_delete.append(contact_id)
    return ids_to_delete


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
