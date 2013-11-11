from django.core.management import BaseCommand
from corehq.apps.reports.models import ReportNotification
from dimagi.utils.couch.database import iter_docs



WHICH_MIGRATION = "second"  # this should be changed to "second" after the first migration has ran.
                           # This should happen in the PR that introduces the schedule report refactor

def first_migrate(notification):
    """
        This adds the interval, day, hour,, and owner_id properties to the doc
    """
    if notification.get("migrated"):  # checks to see if the doc was already migrated.
                                      # Only for use in the lazy migration of new ReportNotifications.
        return False

    if notification.get("day_of_week") == -1 or notification["doc_type"] == "DailyReportNotification":
        notification["interval"] = "daily"
    else:
        notification["interval"] = "weekly"
        notification["day"] = notification["day_of_week"]

    if "hours" in notification:
        notification["hour"] = notification["hours"]

    if notification.get("user_ids") and not notification.get("owner_id"):
        notification["owner_id"] = notification["user_ids"][0]

    notification["migrated"] = True

    return True

def second_migrate(notification):
    """
        This removes the hours, day_of_week, user_ids properties from the doc. changes the doc_type to "ReportNotification"
    """
    if "hours" in notification:
        del notification["hours"]
    if "day_of_week" in notification:
        del notification["day_of_week"]
    if "migrated" in notification:
        del notification["migrated"]
    if "user_ids" in notification:
        del notification["user_ids"]
    notification["doc_type"] = "ReportNotification"
    return True

class Command(BaseCommand):
    args = ""
    help = """
        Loops through every ReportNotification and formats it correctly.
        (Removes user_ids, change `hours` to `hour` and `day_of_week` to `day`)
    """

    def handle(self, *args, **options):
        db = ReportNotification.get_db()
        results = db.view('reportconfig/user_notifications',
            reduce=False,
            include_docs=False,
        ).all()

        migrate = {
            "first": first_migrate,
            "second": second_migrate,
        }[WHICH_MIGRATION]

        notifications_to_save = []
        for notification in iter_docs(db, [r['id'] for r in results]):
            if migrate(notification):
                notifications_to_save.append(notification)

            if len(notifications_to_save) > 100:
                db.bulk_save(notifications_to_save)
                notifications_to_save = []
        db.bulk_save(notifications_to_save)
