from django.db import models
from django.utils.translation import ugettext_noop


class DataManagementRequest(models.Model):
    STATUS_PENDING = 0
    STATUS_IN_PROGRESS = 1
    STATUS_SUCCESS = 2
    STATUS_FAILED = 3
    STATUS_CHOICES = (
        (STATUS_PENDING, ugettext_noop('pending')),
        (STATUS_IN_PROGRESS, ugettext_noop('in progress')),
        (STATUS_SUCCESS, ugettext_noop('successful')),
        (STATUS_FAILED, ugettext_noop('failed'))
    )
    slug = models.CharField(max_length=255, blank=False, null=False)
    created_at = models.DateTimeField(auto_now_add=True)
    initiated_by = models.CharField(max_length=255, blank=True, null=True)

    # timestamps of request runtime
    started_on = models.DateTimeField()
    ended_on = models.DateTimeField()

    # to consider cases modified within range
    from_date = models.DateField(blank=True, null=True)
    till_date = models.DateField(blank=True, null=True)

    error = models.TextField(blank=True, null=True)
    status = models.SmallIntegerField(choices=STATUS_CHOICES, default=STATUS_PENDING)

    def execute(self):
        """
        run the updates through DataManagement
        """
        pass

