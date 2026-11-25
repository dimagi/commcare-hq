from django.utils.translation import gettext as _


class UserUploadError(Exception):
    pass


class MobileWorkerLimitReached(UserUploadError):

    def __init__(self):
        super().__init__(_(
            "This project has reached the mobile worker limit for its subscription plan. "
            "Deactivate other mobile workers or upgrade the plan to add more."
        ))
