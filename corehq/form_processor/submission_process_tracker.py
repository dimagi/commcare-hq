import contextlib
import datetime

from django.db.models import F


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


class ArchiveProcessTracker(object):
    def __init__(self, stub=None):
        self.stub = stub

    def archive_history_updated(self):
        if self.stub:
            self.stub.history_updated = True
            self.stub.save()


@contextlib.contextmanager
def unfinished_submission(instance):
    from couchforms.models import UnfinishedSubmissionStub
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
    unfinished_archive_stub = _get_or_create_unfinished_archive_stub(
        instance.domain, instance.form_id, user_id, archive)
    tracker = ArchiveProcessTracker(unfinished_archive_stub)
    yield tracker
    unfinished_archive_stub.delete()


def _get_or_create_unfinished_archive_stub(domain, form_id, user_id, archive):
    """
    Delete all other competing archive stubs for the same xform

    This makes sure to retain the same row / pk for successive retries of the same failure,
    but creates a new row (and deletes the existing one) for archive/unarchive attempts
    for which either the user or the archive action (archive versus unarchive) differs.

    """
    from couchforms.models import UnfinishedArchiveStub
    defaults = dict(
        user_id=user_id,
        timestamp=datetime.datetime.utcnow(),
        history_updated=False,
        # if archive is False, this is an unarchive stub.
        archive=archive,
        domain=domain,
        attempts=0,
    )
    unfinished_archive_stub, created = UnfinishedArchiveStub.objects.get_or_create(
        xform_id=form_id, defaults=defaults
    )
    if created:
        pass
    elif unfinished_archive_stub.archive == archive \
            and unfinished_archive_stub.user_id == user_id:
        # if the stub already exists and it's "the same" stub
        # then we treat it as an auto retry.
        # It could be the same user repeating the operation,
        # but we'll track that as another attempt at the same operation,
        # not as a new operation. (It's just easier to do that, and it doesn't matter much.)
        unfinished_archive_stub.attempts = F('attempts') + 1
        unfinished_archive_stub.save()
    else:
        UnfinishedArchiveStub.objects.filter(xform_id=form_id).delete()
        unfinished_archive_stub = UnfinishedArchiveStub.objects.create(
            xform_id=form_id, **defaults
        )
    return unfinished_archive_stub
