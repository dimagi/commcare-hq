from collections import defaultdict
from dateutil.relativedelta import relativedelta
import re
from datetime import datetime, timezone, date

from corehq.apps.data_analytics.models import MALTRow


def get_credentials_for_timeframe(activity_level, app_ids):
    months = int(re.search(r'^\d+', activity_level).group())
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
        .values('app_id', 'username', 'user_id', 'month', 'domain')
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
                domain=record["domain"],
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
