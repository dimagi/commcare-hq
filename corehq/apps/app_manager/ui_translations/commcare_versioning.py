from packaging.version import Version

import openpyxl

KEYWORD_PREFIX = 'CommCareVersion='


def get_commcare_version_from_workbook(workbook):
    assert isinstance(workbook, openpyxl.Workbook)
    keywords = workbook.properties.keywords
    if keywords:
        keywords = keywords.split(' ')
        for keyword in keywords:
            if keyword.startswith(KEYWORD_PREFIX):
                version = keyword[len(KEYWORD_PREFIX):]
                try:
                    return str(Version(version))
                except ValueError:
                    pass


def set_commcare_version_in_workbook(workbook, commcare_version):
    try:
        commcare_version = str(Version(commcare_version))
    except ValueError:
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
