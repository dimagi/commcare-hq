# coding=utf-8
from __future__ import absolute_import

from __future__ import unicode_literals
import contextlib
import datetime

from couchforms.models import UnfinishedSubmissionStub, UnfinishedArchiveStub


class SubmissionProcessTracker(object):
    def __init__(self, stub=None):
        self.stub = stub

    def submission_saved(self):
        if self.stub:
            self.stub.saved = True
            self.stub.save()

    def submission_fully_processed(self):
        if self.stub:
            self.stub.delete()


@contextlib.contextmanager
def unfinished_submission(instance):
    unfinished_submission_stub = None
    if not getattr(instance, 'deprecated_form_id', None):
        # don't create stubs for form edits since we don't want to auto-reprocess them
        unfinished_submission_stub = UnfinishedSubmissionStub.objects.create(
            xform_id=instance.form_id,
            timestamp=datetime.datetime.utcnow(),
            saved=False,
            domain=instance.domain,
        )
    tracker = SubmissionProcessTracker(unfinished_submission_stub)
    yield tracker
    tracker.submission_fully_processed()


@contextlib.contextmanager
def unfinished_archive(instance, user_id, archive):
    unfinished_archive_stub = None
    if not getattr(instance, 'deprecated_form_id', None):
        unfinished_archive_stub = UnfinishedArchiveStub.objects.create(
            user_id=user_id,
            xform_id=instance.form_id,
            timestamp=datetime.datetime.utcnow(),
            # if archive is False, this is an unarchive stub.
            archive=archive,
            domain=instance.domain,
        )
    yield
    unfinished_archive_stub.delete()
