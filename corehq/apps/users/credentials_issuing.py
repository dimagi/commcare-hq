from collections import defaultdict
from django.conf import settings
from dateutil.relativedelta import relativedelta
import requests
from datetime import datetime, timezone, date

from dimagi.utils.logging import notify_exception

from corehq.apps.data_analytics.models import MALTRow


CREDENTIAL_TYPE = 'APP_ACTIVITY'
MAX_CREDENTIALS_PER_REQUEST = 200


def get_credentials_for_timeframe(activity_level, app_ids):
    from corehq.apps.app_manager.models import CredentialApplication
    months = CredentialApplication.months_for_activity_level(activity_level)
    now = datetime.now(timezone.utc)
    start_date = date(now.year, now.month, now.day) - relativedelta(months=months)
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

        has_required_months = len(user_months[combined_user_app_id]) >= months
        if has_required_months and combined_user_app_id not in combined_user_app_ids:
            user_credentials.append(UserCredential(
                user_id=record["user_id"],
                app_id=record["app_id"],
                username=record["username"],
                domain=record["domain_name"],
                type=activity_level,
            ))
            combined_user_app_ids.add(combined_user_app_id)

    return user_credentials


def get_app_ids_by_activity_level():
    from corehq.apps.app_manager.models import CredentialApplication

    credential_apps = CredentialApplication.objects.all()
    app_ids_by_level = defaultdict(list)
    for app in credential_apps:
        app_ids_by_level[app.activity_level].append(app.app_id)
    return app_ids_by_level


def submit_new_credentials():
    credentials_to_submit, credential_id_groups_to_update = get_credentials_to_submit()
    if not credentials_to_submit:
        return

    total = len(credentials_to_submit)
    for start in range(0, total, MAX_CREDENTIALS_PER_REQUEST):
        end = min(total, start + MAX_CREDENTIALS_PER_REQUEST)
        credentials_to_submit_batch = credentials_to_submit[start:end]
        credential_id_groups_to_update_batch = credential_id_groups_to_update[start:end]

        response = requests.post(
            settings.CONNECTID_CREDENTIALS_URL,
            json={
                "credentials": credentials_to_submit_batch
            },
            auth=(settings.CONNECTID_CLIENT_ID, settings.CONNECTID_SECRET_KEY),
        )
        response.raise_for_status()
        mark_credentials_as_issued(response, credential_id_groups_to_update_batch)


def get_credentials_to_submit():
    from corehq.apps.users.models import ConnectIDUserLink, UserCredential

    user_credentials = UserCredential.objects.filter(issued_on=None)
    if not user_credentials:
        return [], []

    app_ids = []
    usernames = []
    for user_cred in user_credentials:
        app_ids.append(user_cred.app_id)
        usernames.append(user_cred.username)

    connectid_links = ConnectIDUserLink.objects.filter(
        commcare_user__username__in=usernames
    )
    connectid_username_by_commcare_username = {
        link.commcare_user.username: link.connectid_username for link in connectid_links
    }

    app_names_by_id = get_app_names_by_id(app_ids)
    credentials_to_submit = {}
    credential_id_groups_to_update = defaultdict(list)
    for user_cred in user_credentials:
        connectid_username = connectid_username_by_commcare_username.get(user_cred.username)
        if not connectid_username:
            continue  # Skip these users as they still need to set up their PersonalID account

        key = f'{user_cred.app_id}:{user_cred.type}'
        if key not in credentials_to_submit:
            credentials_to_submit[key] = {
                'usernames': [],
                'title': app_names_by_id[user_cred.app_id],
                'type': CREDENTIAL_TYPE,
                'level': user_cred.type,
                'slug': user_cred.app_id,
                'app_id': user_cred.app_id,
            }

        credentials_to_submit[key]['usernames'].append(connectid_username)
        credential_id_groups_to_update[key].append(user_cred.id)

    return list(credentials_to_submit.values()), list(credential_id_groups_to_update.values())


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


def get_app_names_by_id(app_ids):
    from corehq.apps.app_manager.dbaccessors import get_apps_by_id

    apps = get_apps_by_id(domain=None, app_ids=app_ids)
    return {app.id: app.name for app in apps}
