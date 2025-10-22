from collections import defaultdict
from django.conf import settings
from dateutil.relativedelta import relativedelta
import requests
from datetime import datetime, timezone, date

from dimagi.utils.logging import notify_exception
from dimagi.utils.chunked import chunked

from corehq.apps.data_analytics.models import MALTRow


CREDENTIAL_TYPE = 'APP_ACTIVITY'
MAX_CREDENTIALS_PER_REQUEST = 200
MAX_USERNAMES_PER_CREDENTIAL = 200


def get_credentials_for_timeframe(activity_level, app_ids):
    from corehq.apps.users.models import months_for_activity_level
    months = months_for_activity_level(activity_level)
    now = datetime.now(timezone.utc)
    # Add 1 to calculate for previous month as well. This is to prevent scenarios like late submissions causing
    # potential credentials to be missed.
    start_date = date(now.year, now.month, now.day) - relativedelta(months=months + 1)
    user_months_activity = (
        MALTRow.objects
        .filter(
            month__gte=start_date,
            num_of_forms__gte=1,
            app_id__in=app_ids,
            user_type='CommCareUser',
            is_app_deleted=False,
        )
        .values('app_id', 'username', 'user_id', 'month', 'domain_name')
        .distinct()
    )
    return _filter_users_with_complete_months(user_months_activity, months, activity_level)


def _filter_users_with_complete_months(data, months, activity_level):
    """
    Filter data to only include records where each user has entries for all distinct months.
    """
    from corehq.apps.users.models import UserCredential

    user_months = defaultdict(set)
    user_credentials = []
    combined_user_app_ids = set()  # Keep track of which user-app combos have had creds created
    for record in data:
        combined_user_app_id = record["user_id"] + record["app_id"]
        user_months[combined_user_app_id].add(record["month"])

        has_required_months = has_consecutive_months(user_months[combined_user_app_id], months)
        if has_required_months and combined_user_app_id not in combined_user_app_ids:
            user_credentials.append(UserCredential(
                user_id=record["user_id"],
                app_id=record["app_id"],
                username=record["username"],
                domain=record["domain_name"],
                activity_level=activity_level,
            ))
            combined_user_app_ids.add(combined_user_app_id)

    return user_credentials


def has_consecutive_months(month_dates, required_months):
    if len(month_dates) < required_months:
        return False

    # Dates are converted into a single linear month index so that consecutive
    # calendar months always differ by 1
    nums = sorted({d.year * 12 + d.month for d in month_dates})
    streak = 1
    for i in range(1, len(nums)):
        if nums[i] == nums[i - 1] + 1:
            streak += 1
        else:
            streak = 1
        if streak >= required_months:
            return True
    return False


def get_app_ids_by_activity_level():
    from corehq.apps.app_manager.models import CredentialApplication

    credential_apps = CredentialApplication.objects.all()
    app_ids_by_level = defaultdict(list)
    for app in credential_apps:
        app_ids_by_level[app.activity_level].append(app.app_id)
    return app_ids_by_level


def submit_new_credentials():
    from corehq.apps.users.models import UserCredential

    user_credentials = UserCredential.objects.filter(issued_on=None)

    app_names_by_id = get_app_names_by_id(user_credentials)
    username_cred_id_dict = get_username_cred_id_dict(user_credentials)

    cred_id_groups = []
    creds_to_submit = []
    try:
        for app_id_level, username_cred_id_list in username_cred_id_dict.items():
            app_id, activity_level = app_id_level
            for username_cred_id_chunk in chunked(username_cred_id_list, MAX_USERNAMES_PER_CREDENTIAL):
                usernames, cred_ids = zip(*username_cred_id_chunk)
                creds_to_submit.append({
                    'credentials': {
                        'usernames': usernames,
                        'title': app_names_by_id[app_id],
                        'type': CREDENTIAL_TYPE,
                        'level': activity_level,
                        'slug': app_id,
                        'app_id': app_id,
                    }
                })
                cred_id_groups.append(cred_ids)
                if len(creds_to_submit) >= MAX_CREDENTIALS_PER_REQUEST:
                    submit_credentials(creds_to_submit, cred_id_groups)
                    creds_to_submit = []
                    cred_id_groups = []
        if creds_to_submit:
            submit_credentials(creds_to_submit, cred_id_groups)
    except (requests.ConnectionError, requests.HTTPError, requests.Timeout, requests.RequestException) as e:
        notify_exception(
            None,
            "Failed to submit credentials to PersonalID",
            details={
                'error': str(e),
            }
        )


def submit_credentials(credentials_to_submit, cred_id_groups):
    """
    If the request fails a `ConnectionError` or `ResponseError` will be raised.
    This function can also raise `HttpError` if the response status code is not 2xx.
    """
    response = requests.post(
        settings.CONNECTID_CREDENTIALS_URL,
        json={
            'credentials': credentials_to_submit
        },
        auth=(settings.CONNECTID_CREDENTIALS_CLIENT_ID, settings.CONNECTID_CREDENTIALS_CLIENT_SECRET),
    )
    response.raise_for_status()
    mark_credentials_as_issued(response, cred_id_groups)


def get_username_cred_id_dict(user_credentials):
    """
    Returns a dict in the following format:
    {
        (app_id, activity_level): [(connectid_username, user_cred.id), ...]
    }
    """
    username_map = get_connectid_username_by_commcare_username(user_credentials)
    username_cred_id_dict = defaultdict(list)
    for user_cred in user_credentials:
        if user_cred.username not in username_map:
            # Skip users who still need to set up their PersonalID account
            continue
        app_id_level = (user_cred.app_id, user_cred.activity_level)
        cid_username = username_map[user_cred.username]
        username_cred_id = (cid_username, user_cred.id)
        username_cred_id_dict[app_id_level].append(username_cred_id)
    return username_cred_id_dict


def get_connectid_username_by_commcare_username(user_credentials):
    from corehq.apps.users.models import ConnectIDUserLink
    usernames = [c.username for c in user_credentials]
    connectid_links = ConnectIDUserLink.objects.filter(
        commcare_user__username__in=usernames
    )
    return {
        link.commcare_user.username: link.connectid_username for link in connectid_links
    }


def mark_credentials_as_issued(response, credential_id_groups):
    from corehq.apps.users.models import UserCredential

    success_indices = set(response.json().get('success', []))
    failed_indices = set(response.json().get('failed', []))
    success_credential_ids = []
    failed_credential_ids = []
    for i, id_group in enumerate(credential_id_groups):
        if i in success_indices:
            success_credential_ids += id_group
        elif i in failed_indices:
            failed_credential_ids += id_group

    issued_date = datetime.now(timezone.utc)
    UserCredential.objects.filter(id__in=success_credential_ids).update(issued_on=issued_date)

    if failed_credential_ids:
        notify_exception(
            None,
            f"Failed to submit {len(failed_credential_ids)} credentials to PersonalID",
            details={
                'failed_credential_ids': failed_credential_ids,
            }
        )


def get_app_names_by_id(user_credentials):
    from corehq.apps.app_manager.models import Application
    app_ids_dict = {}
    keys = []
    for user_cred in user_credentials:
        app_ids_dict[user_cred.app_id] = user_cred.app_id
        keys.append([user_cred.domain, user_cred.app_id])

    result = Application.get_db().view(
        'app_manager/applications_brief',
        keys=keys).all()
    app_names_by_id = {r['value']['_id']: r['value']['name'] for r in result}
    return app_ids_dict | app_names_by_id
