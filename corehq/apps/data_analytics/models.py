from django.db import models


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
    is_web_user = models.BooleanField()
    domain_name = models.TextField(db_index=True)
    num_of_forms = models.TextField()

    YES = 'yes'
    NO = 'no'
    NOT_SET = 'not_set'
    WAM_PAM_CHOICES = (
        (YES, 'Yes'),
        (NO, 'No'),
        (NOT_SET, 'Not Set')
    )
    app_id = models.TextField()
    wam = models.CharField(choices=WAM_PAM_CHOICES, default=NOT_SET, max_length=7)
    pam = models.CharField(choices=WAM_PAM_CHOICES, default=NOT_SET, max_length=7)
    is_app_deleted = models.BooleanField()

    class Meta:
        unique_together = ('month', 'domain_name', 'user_id', 'app_id')
