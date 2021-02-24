from django.conf import settings

from corehq.apps.accounting.models import Subscription, BillingAccount


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


def hubspot_enabled_for_user(couch_user):
    if is_email_blocked_from_hubspot(couch_user.username):
        return False
    for domain in couch_user.get_domains():
        if is_domain_blocked_from_hubspot(domain):
            return False
    return couch_user.analytics_enabled


def hubspot_enabled_for_email(email_address):
    from corehq.apps.users.models import CouchUser
    user = CouchUser.get_by_username(email_address)
    return hubspot_enabled_for_user(user) if user else True


def get_blocked_hubspot_domains():
    return list(Subscription.visible_objects.filter(
        account__block_hubspot_data_for_all_users=True,
        is_active=True,
        account__is_active=True,
    ).values_list('subscriber__domain', flat=True))


def get_blocked_hubspot_email_domains():
    return [_email for email_list in BillingAccount.objects.filter(
        is_active=True,
    ).exclude(
        block_email_domains_from_hubspot=[],
    ).values_list(
        'block_email_domains_from_hubspot',
        flat=True,
    ) for _email in email_list]


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


