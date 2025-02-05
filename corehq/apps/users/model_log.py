from enum import Enum

from corehq.apps.users.models import UserHistory, InvitationHistory


class UserModelAction(Enum):
    CREATE = UserHistory.CREATE
    UPDATE = UserHistory.UPDATE
    DELETE = UserHistory.DELETE
    CLEAR = UserHistory.CLEAR


class InviteModelAction(Enum):
    CREATE = InvitationHistory.CREATE
    UPDATE = InvitationHistory.UPDATE
    DELETE = InvitationHistory.DELETE
