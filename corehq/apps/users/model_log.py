from enum import Enum

from corehq.apps.users.models import UserHistory


class UserModelAction(Enum):
    CREATE = UserHistory.CREATE
    UPDATE = UserHistory.UPDATE
    DELETE = UserHistory.DELETE
    CLEAR = UserHistory.CLEAR
