from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime
from django.conf import settings

from corehq.toggles import was_user_created_after


class StaticUINotify(object):
    """
    Useful for handling more complex & dismissable UI notifications
    that might appear inline in the UI. This is still in it's early stages
    and used in App Builder. Will build upon this as we go along.
    """

    def __init__(self, slug,
                 only_visible_for_users_created_before=None,
                 only_visible_for_users_created_after=None,
                 starts_on=None,
                 ends_on=None):
        """
        :param slug: should have the format of something_descriptive_month_year
                     e.g. app_builder_publish_page_08_2017
        :param only_visible_for_users_created_before: datetime or None
        :param only_visible_for_users_created_after: datetime or None
        :param starts_on: datetime or None
        :param ends_on: datetime or None
        """
        # slug should have the format of something_descriptive_month_year
        # e.g. app_builder_publish_page_08_2017
        self.slug = slug
        self.visible_to_users_before = only_visible_for_users_created_before
        self.visible_to_users_after = only_visible_for_users_created_after
        self.starts_on = starts_on
        self.ends_on = ends_on

    def enabled(self, request):
        if settings.ENTERPRISE_MODE:
            return False

        if hasattr(request, 'user'):
            from corehq.apps.notifications.models import DismissedUINotify

            today = datetime.now()

            if self.starts_on is not None and self.starts_on >= today:
                return False

            if self.ends_on is not None and self.ends_on <= today:
                return False

            if (self.visible_to_users_before is not None
                and was_user_created_after(
                    request.user.username,
                    self.visible_to_users_before)):
                return False

            if (self.visible_to_users_after is not None
                and not was_user_created_after(
                    request.user.username,
                    self.visible_to_users_after)):
                return False

            return not DismissedUINotify.is_notification_dismissed(
                request.user, self.slug
            )
        return False


APP_BUILDER_PUBLISH = StaticUINotify(
    'app_builder_publish_jul2017',
    ends_on=datetime(2017, 8, 14, 20),
    only_visible_for_users_created_before=datetime(2017, 7, 14, 20),
)


APP_BUILDER_RELEASE = StaticUINotify(
    'app_builder_release_jul2017',
    ends_on=datetime(2017, 8, 14, 20),
    only_visible_for_users_created_before=datetime(2017, 5, 16, 20),
)

APP_BUILDER_ADD_ONS = StaticUINotify(
    'app_builder_add_ons_jul2017',
    ends_on=datetime(2017, 8, 31, 20),
    only_visible_for_users_created_before=datetime(2017, 7, 31, 20),
)

REPORT_BUILDER_V2 = StaticUINotify(
    'report_builder_v2_nov2017',
    ends_on=datetime(2017, 12, 22, 20),
    only_visible_for_users_created_before=datetime(2017, 11, 5, 20),
)

MESSAGING_DASHBOARD = StaticUINotify(
    'messaging_dashboard_may2018',
    ends_on=datetime(2018, 7, 1),
    only_visible_for_users_created_before=datetime(2018, 5, 25),
)

ABILITY_TO_HIDE_TRANSLATIONS = StaticUINotify(
    'ability_to_hide_translations',
    ends_on=datetime(2018, 7, 1),
    only_visible_for_users_created_before=datetime(2018, 5, 31),
)

DATA_FIND_BY_ID = StaticUINotify(
    'data_find_by_id_sept2018',
    ends_on=datetime(2018, 11, 1),
    only_visible_for_users_created_before=datetime(2018, 9, 26),
)

FORMS_CASES_URL_IN_EXPORTS = StaticUINotify(
    'forms_cases_url_in_exports_jan2019',
    ends_on=datetime(2019, 2, 14)
)

USERS_PERMISSIONS_UPDATES = StaticUINotify(
    'users_permissions_updates_april2019',
    ends_on=datetime(2019, 6, 3),
    only_visible_for_users_created_before=datetime(2019, 4, 3),
)

ECD_PREVIEW_UPDATE = StaticUINotify(
    'ecd_preview_update_jul2019',
    ends_on=datetime(2019, 9, 12),
)
