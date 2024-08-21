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
