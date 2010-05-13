import os

from django.conf import settings

# make our directories if they're not there
for dir in [settings.RECEIVER_SUBMISSION_PATH,
            settings.RECEIVER_ATTACHMENT_PATH,
            settings.RECEIVER_EXPORT_PATH]:
    if not os.path.isdir(dir):
        os.mkdir(dir)
