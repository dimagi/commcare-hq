from django.db import models

from corehq.apps.app_manager.const import AMPLIFIES_YES, AMPLIFIES_NO, AMPLIFIES_NOT_SET


class MALTRow(models.Model):
    """
        Specifies a row for 'Monthly Aggregate Lite Table (MALT)'
        See https://docs.google.com/document/d/1QQ3tzFPs6TWiPiah6YUBCrFILKih6OcJV7444i50o1U/edit
    """
    month = models.DateField(db_index=True)

    # Using TextField instead of CharField, because...
    # postgres doesn't differentiate between Char/Text and there is no hard max-length limit
    user_id = models.TextField()
    username = models.TextField()
    email = models.EmailField()
    user_type = models.TextField()

    domain_name = models.TextField(db_index=True)
    num_of_forms = models.PositiveIntegerField()
    app_id = models.TextField()
    device_id = models.TextField(blank=True, null=True)
    is_app_deleted = models.BooleanField(default=False)

    YES = True  # equivalent to app_manager.const.AMPLIFIES_YES
    NO = False  # equivalent to app_manager.const.AMPLIFIES_NO
    NOT_SET = None  # equivalent to app_manager.const.AMPLIFIES_NOT_SET
    wam = models.NullBooleanField(default=NOT_SET)
    pam = models.NullBooleanField(default=NOT_SET)
    AMPLIFY_COUCH_TO_SQL_MAP = {
        AMPLIFIES_YES: YES,
        AMPLIFIES_NO: NO,
        AMPLIFIES_NOT_SET: NOT_SET
    }
    use_threshold = models.PositiveSmallIntegerField(default=15)
    experienced_threshold = models.PositiveSmallIntegerField(default=3)

    class Meta:
        unique_together = ('month', 'domain_name', 'user_id', 'app_id', 'device_id')

    @classmethod
    def get_unique_fields(cls):
        return list(cls._meta.unique_together[0])
