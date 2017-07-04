class StaticUINotify(object):
    """
    Useful for handling more complex & dismissable UI notifications
    that might appear inline in the UI. This is still in it's early stages
    and used in App Builder. Will build upon this as we go along.
    """

    def __init__(self, slug, label):
        self.slug = slug
        self.label = label

    def enabled(self, request):
        if hasattr(request, 'user'):
            from corehq.apps.notifications.models import DismissedUINotify
            return not DismissedUINotify.is_notification_dismissed(
                request.user, self.slug
            )
        return False


TEST_UI_NOTIFY = StaticUINotify(
    'first_ui_notify',
    'Test a UI Notification.'
)
