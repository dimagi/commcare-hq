from __future__ import absolute_import
from __future__ import unicode_literals
from casexml.apps.phone.exceptions import BadVersionException

V1 = "1.0"
V2 = "2.0"
V3 = "3.0"
DEFAULT_VERSION = V1
LEGAL_VERSIONS = [V1, V2, V3]

V2_NAMESPACE = "http://commcarehq.org/case/transaction/v2"

NS_VERSION_MAP = {
    V2: V2_NAMESPACE,
}

NS_REVERSE_LOOKUP_MAP = dict((v, k) for k, v in NS_VERSION_MAP.items())


def check_version(version):
    if version not in LEGAL_VERSIONS:
        raise BadVersionException(
            "%s is not a legal version, must be one of: %s" %
            (version, ", ".join(LEGAL_VERSIONS))
        )
