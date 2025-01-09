import re

from corehq.apps.builds.models import CommCareBuild, CommCareBuildConfig


def get_all_versions(versions):
    """
    Returns a list of all versions found in the database,
    plus those in the optional list parameter.
    """
    db = CommCareBuild.get_db()
    results = db.view('builds/all', group_level=1).all()
    versions += [result['key'][0] for result in results]
    return sorted(list(set(versions)))


def get_default_build_spec():
    return CommCareBuildConfig.fetch().get_default()


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


def get_latest_version_at_time(config, target_time, cache=None):
    """
    Get the latest CommCare version that was available at a given time.
    Excludes superuser-only versions.
    Menu items are already in chronological order (newest last).
    If no target time is provided, return the latest version available now.

    Args:
        config: CommCareBuildConfig instance
        target_time: datetime, or None for latest version
        cache: Dictionary for per-request caching
    """
    if cache is None:
        cache = {}

    if not target_time:
        return config.get_default().version

    # Iterate through menu items in reverse (newest to oldest)
    for item in reversed(config.menu):
        if item.superuser_only:
            continue
        build_time = get_build_time(item.build.version, cache)
        if build_time and build_time <= target_time:
            return item.build.version

    return None


def get_build_time(version, cache=None):
    if cache is None:
        cache = {}

    if version in cache:
        return cache[version]

    try:
        build = CommCareBuild.get_build(version, latest=True)
    except KeyError:
        cache[version] = None
        return None

    build_time = build.time if build and build.time else None
    cache[version] = build_time
    return build_time


def is_out_of_date(version_in_use, latest_version):
    """
    Check if the version in use is out of date compared to the latest version.
    params:
        version_in_use: str, the version in use
        latest_version: str, the latest version
    returns:
        bool, True if the version in use is out of date, False otherwise
    """
    version_in_use_tuple = _parse_version(version_in_use)
    latest_version_tuple = _parse_version(latest_version)
    if not version_in_use_tuple or not latest_version_tuple:
        return False
    return version_in_use_tuple < latest_version_tuple


def _parse_version(version_str):
    """Convert version string to comparable tuple, padding with zeros."""
    SEMANTIC_VERSION_PARTS = 3  # Major, minor, patch
    if version_str:
        try:
            version_parts = [int(n) for n in version_str.split('.')]
            # Pad the version tuple to ensure both versions have the same length
            return tuple(version_parts + [0] * (SEMANTIC_VERSION_PARTS - len(version_parts)))
        except (ValueError, AttributeError):
            return None
    return None
