DATETIME_PATTERN = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z"


def strip_xml(xmlstr: str) -> str:
    return ''.join((l.strip() for l in xmlstr.split('\n'))).replace('»', '')
