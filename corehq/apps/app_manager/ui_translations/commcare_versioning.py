from looseversion import LooseVersion
from packaging.version import Version, InvalidVersion

import openpyxl

KEYWORD_PREFIX = 'CommCareVersion='


def get_strict_commcare_version_string(version):
    """This replaces our usage of distutils.version.StrictVersion when ensuring
    that a version numbering format correctly follows an expected major.minor.patch versioning scheme.
    """
    if isinstance(version, LooseVersion):
        version = version.vstring
    try:
        strict_version = Version(version)
        if strict_version.micro > 0:
            return '{}.{}.{}'.format(
                strict_version.major, strict_version.minor, strict_version.micro
            )
        return '{}.{}'.format(strict_version.major, strict_version.minor)
    except InvalidVersion:
        return


def get_commcare_version_from_workbook(workbook):
    assert isinstance(workbook, openpyxl.Workbook)
    keywords = workbook.properties.keywords
    if keywords:
        keywords = keywords.split(' ')
        for keyword in keywords:
            if keyword.startswith(KEYWORD_PREFIX):
                version = keyword[len(KEYWORD_PREFIX):]
                version = get_strict_commcare_version_string(version)
                if version is None:
                    pass
                return version


def set_commcare_version_in_workbook(workbook, commcare_version):
    commcare_version = get_strict_commcare_version_string(commcare_version)
    if commcare_version is None:
        return

    assert isinstance(workbook, openpyxl.Workbook)
    keywords = workbook.properties.keywords
    if keywords:
        keywords = [keyword for keyword in keywords.split(' ')
                    if not keyword.startswith(KEYWORD_PREFIX)]
    else:
        keywords = []

    keywords = ['{}{}'.format(KEYWORD_PREFIX, commcare_version)] + keywords
    workbook.properties.keywords = ' '.join(keywords)
