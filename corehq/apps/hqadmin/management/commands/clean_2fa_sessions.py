from looseversion import LooseVersion
from getpass import getpass
from importlib import import_module
from pkg_resources import DistributionNotFound, get_distribution

from django.conf import settings
from django.core.cache import caches
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Remove outdated/sensitive information from active Django sessions. "
        "See https://github.com/Bouke/django-two-factor-auth/security/advisories/GHSA-vhr6-pvjm-9qwf"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--one-session',
            action='store_true',
            default=False,
            help='Lookup one session only (will prompt for a session key).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='Count the number of sessions that would be affected, '
                 'but do not modify them.',
        )

    def handle(self, one_session=False, dry_run=False, **options):
        if dry_run:
            print("DRY RUN sessions will not be modified")

        tf_ver = get_two_factor_version()
        if tf_ver and LooseVersion(tf_ver) < LooseVersion("1.12"):
            print(f"WARNING old/insecure django-two-factor-auth version detected: {tf_ver}")
            print("Please run this tool again after upgrading.")
        else:
            print(f"found django-two-factor-auth version {tf_ver}")

        print("scanning sessions...")
        count = i = 0
        for i, session in enumerate(iter_sessions(one_session), start=1):
            if i % 10000 == 0:
                print(f"processed {i} sessions")
            if has_sensitive_info(session):
                count += 1
                if not dry_run:
                    sanitize(session)

        if dry_run:
            print(f"DRY RUN {count} of {i} sessions need to be sanitized")
        else:
            print(f"Sanitized {count} of {i} sessions")


def sanitize(session):
    for data in iter_wizard_login_views(session):
        del data["step_data"]
        del data["validated_step_data"]
    session.save()
    assert not has_sensitive_info(session)


def iter_sessions(one_session):
    """Iterate over one or all existing django sessions

    Assumes that redis is the default cache in which all sessions are stored.
    """
    assert settings.SESSION_ENGINE == "django.contrib.sessions.backends.cache", \
        f"unsupported session engine: {settings.SESSION_ENGINE}"
    engine = import_module(settings.SESSION_ENGINE)

    if one_session:
        session_key = getpass(prompt="Session key: ")
        yield engine.SessionStore(session_key)
        return

    cache = caches[settings.SESSION_CACHE_ALIAS]
    prefix_length = len(engine.SessionStore.cache_key_prefix)
    for key in cache.iter_keys(engine.SessionStore.cache_key_prefix + "*"):
        session_key = key[prefix_length:]
        yield engine.SessionStore(session_key)


def has_sensitive_info(session):
    def has_key(data, path):
        value = data
        for name in path:
            if not isinstance(value, dict) or name not in value:
                return False
            value = value[name]
        return True
    return any(
        has_key(data, STEP_DATA_PATH) or has_key(data, VALIDATED_STEP_DATA_PATH)
        for data in iter_wizard_login_views(session)
    )


def iter_wizard_login_views(session):
    for key, data in session.items():
        if key.startswith("wizard_") and key.endswith("_login_view"):
            yield data


STEP_DATA_PATH = ["step_data", "auth", "auth-password"]
VALIDATED_STEP_DATA_PATH = ["validated_step_data", "auth", "password"]


def get_two_factor_version():
    try:
        dist = get_distribution("django-two-factor-auth")
    except DistributionNotFound:
        return None
    return dist.version
