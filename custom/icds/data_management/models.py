from datetime import datetime

from django.db import models
from django.utils.translation import ugettext_noop

from custom.icds.data_management.const import DATA_MANAGEMENT_TASKS


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
    STATUSES = [STATUS_PENDING, STATUS_IN_PROGRESS, STATUS_SUCCESS, STATUS_FAILED]
    slug = models.CharField(max_length=255, blank=False, null=False)
    domain = models.CharField(max_length=255, blank=False, null=False)
    db_alias = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    initiated_by = models.CharField(max_length=255, blank=False, null=False)

    # timestamps of request runtime
    started_on = models.DateTimeField(blank=True, null=True)
    ended_on = models.DateTimeField(blank=True, null=True)

    # to consider cases modified within range
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)

    error = models.TextField(blank=True, null=True)
    status = models.SmallIntegerField(choices=STATUS_CHOICES, default=STATUS_PENDING)

    def execute(self):
        """
        run the updates through DataManagement
        """
        self._set_in_progress()
        if self.slug not in DATA_MANAGEMENT_TASKS:
            self._note_error("Unexpected slug %s" % self.slug)
            return None, None, {}
        else:
            try:
                processed, skipped, logs = self._perform_task()
            except Exception as e:
                self._note_error(str(e))
                raise
            else:
                self.status = self.STATUS_SUCCESS
            finally:
                self.ended_on = datetime.utcnow()
                self.save()
        return processed, skipped, logs

    def _set_in_progress(self):
        self.status = self.STATUS_IN_PROGRESS
        self.started_on = datetime.utcnow()
        self.save()

    def _note_error(self, message):
        self.error = message
        self.status = self.STATUS_FAILED

    def _perform_task(self):
        task_to_run = DATA_MANAGEMENT_TASKS[self.slug](self.domain, self.db_alias, self.start_date, self.end_date)
        iteration_key = "%s-%s-%s-%s-%s" % (self.slug, self.start_date, self.end_date, self.initiated_by,
                                            self.started_on)
        return task_to_run.run(iteration_key)
