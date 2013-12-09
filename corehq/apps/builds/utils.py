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
