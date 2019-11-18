from django.db import models


class MigratedReminder(models.Model):
    """
    This model is used to keep track of where migrated reminders came from
    in the new reminders framework. It maps an old CaseReminderHandler doc_id
    to either a broadcast or a rule in the new reminders framework.
    """

    # The CaseReminderHandler doc_id from the old reminders framework.
    handler_id = models.CharField(max_length=126, unique=True)

    # If the CaseReminderHandler was a broadcast, this is the corresponding
    # migrated broadcast.
    broadcast = models.ForeignKey('scheduling.ImmediateBroadcast', null=True, on_delete=models.PROTECT)

    # If the CaseReminderHandler was a conditional reminder, this is the
    # corresponding migrated rule for the conditional alert.
    rule = models.ForeignKey('data_interfaces.AutomaticUpdateRule', null=True, on_delete=models.PROTECT)
