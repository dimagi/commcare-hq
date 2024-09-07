import sys

from .tools import nottest as nottest_tool


def create_nose_virtual_package():
    sys.modules['nose.tools'] = VirtualNose.tools


class VirtualNose:
    """Legacy namespace for tests written before pytest"""
    class tools:
        nottest = nottest_tool
