import re
from .models import CommCareBuild, CommCareBuildConfig


def get_all_versions(versions=None):
    """
    Returns a list of all versions found in the database,
    plus those in the optional list parameter.
    """
    versions = versions or []
    db = CommCareBuild.get_db()
    results = db.view('builds/all', group_level=1).all()
    versions += [result['key'][0] for result in results]
    return sorted(list(set(versions)))


def get_default_build_spec(application_version):
    return CommCareBuildConfig.fetch().get_default(application_version)


def extract_build_info_from_filename(content_disposition):
    """

    >>> extract_build_info_from_filename(
    ...     'attachment; filename=CommCare_CommCare_2.13_32703_artifacts.zip'
    ... )
    ('2.13', 32703)
    >>> try:
    ...     extract_build_info_from_filename('foo')
    ... except ValueError as e:
    ...     print e
    Could not find filename like 'CommCare_CommCare_([\\\\d\\\\.]+)_(\\\\d+)_artifacts.zip' in 'foo'

    """
    pattern = r'CommCare_CommCare_([\d\.]+)_(\d+)_artifacts.zip'
    match = re.search(pattern, content_disposition)
    if match:
        version, number = match.groups()
        return version, int(number)
    else:
        raise ValueError('Could not find filename like {!r} in {!r}'.format(
            pattern, content_disposition))
