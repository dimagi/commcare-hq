"""
Minimalist implementation of a version parser.

Duck-types semantic_version.Version where we need it.
"""
import re
from typing import Any, TypeVar

VersionType = TypeVar('VersionType', bound='Version')


class Version:
    def __init__(self, version_str: str):
        match = re.match(r"^(\d+)\.(\d+)\.(\d+)", version_str)
        if not match:
            raise ValueError('Version is expected to be in the format '
                             '"major.minor.patch", where "major", "minor" and '
                             '"patch" are integers.')
        self.major = int(match.group(1))
        self.minor = int(match.group(2))
        self.patch = int(match.group(3))

    def __str__(self):
        return f"{self.major}.{self.minor}.{self.patch}"

    @property
    def __key(self):
        return (self.major, self.minor, self.patch)

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.__key == other.__key
        raise NotImplementedError

    def __hash__(self):
        return hash(self.__key)

    def __gt__(self, other):
        if isinstance(other, self.__class__):
            return self.__key > other.__key
        raise NotImplementedError

    @classmethod
    def coerce(cls, version_str: str) -> VersionType:
        if not version_str:
            raise ValueError("Unable to parse blank version")
        args = version_str.split(".")
        if not is_int(args[0]):
            raise ValueError("Unable to determine major version number")
        numbers = [a for a in args if is_int(a)] + 3 * ["0"]
        return Version(".".join(numbers[:3]))


def is_int(value: Any) -> bool:
    try:
        return float(value).is_integer()
    except ValueError:
        return False
