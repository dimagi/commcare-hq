from enum import Enum

from django.contrib.admin.models import ADDITION, CHANGE, DELETION


class ModelAction(Enum):
    CREATE = ADDITION
    UPDATE = CHANGE
    DELETE = DELETION
