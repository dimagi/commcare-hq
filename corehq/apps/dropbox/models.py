import os

from django.db import models
from django.contrib.auth.models import User

from .exceptions import DropboxUploadAlreadyInProgress
from .tasks import upload


class DropboxUploadHelper(models.Model):
    """
    This class is for working with dropbox uploads. It saves metadata to the database, stores the progress of
    the upload, and ensures multiple uploads of the same file does not occur.
    """
    dest = models.CharField(max_length=255)
    src = models.CharField(max_length=255)
    progress = models.DecimalField(default=0, decimal_places=2, max_digits=3)
    download_id = models.CharField(max_length=255, db_index=True)
    user = models.ForeignKey(User)

    # If this field is set then the task has failed
    failure_reason = models.CharField(max_length=255, null=True, default=None)

    initiated = False

    class Meta:
        app_label = 'dropbox'

    @classmethod
    def create(cls, token, **kwargs):
        download_id = kwargs.get('download_id')

        existing_uploader = DropboxUploadHelper.objects.filter(download_id=download_id).first()
        if existing_uploader and existing_uploader.failure_reason is None:
            raise DropboxUploadAlreadyInProgress(
                u'There already exists an upload with the download id: {}'.format(download_id)
            )

        helper = cls.objects.create(
            src=kwargs.get('src'),
            dest=kwargs.get('dest'),
            download_id=download_id,
            user=kwargs.get('user'),
        )
        helper.token = token
        return helper

    def upload(self, max_size=None, max_retries=3):
        if self.initiated:
            raise DropboxUploadAlreadyInProgress(u'The upload has already been initiated')
        size = max_size or os.path.getsize(self.src)
        upload.delay(self.id, self.token, size, max_retries)
        self.initiated = True
