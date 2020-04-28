"""
Migrate Dhis2Connection instances to ConnectionSettings model
"""
from django.core.management import BaseCommand

from corehq.motech.const import BASIC_AUTH
from corehq.motech.dhis2.dbaccessors import get_dataset_maps
from corehq.motech.dhis2.models import Dhis2Connection
from corehq.motech.models import ConnectionSettings


class Command(BaseCommand):

    def handle(self, **options):
        for dhis2_conn in Dhis2Connection.objects.all():
            if conn_settings_exists(dhis2_conn):
                continue
            conn_settings = create_conn_settings(dhis2_conn)
            link_data_set_maps(conn_settings)


def conn_settings_exists(dhis2_conn: Dhis2Connection) -> bool:
    """
    Does a ConnectionSettings instance exist for ``dhis2_conn``.
    """
    return ConnectionSettings.objects\
        .filter(domain=dhis2_conn.domain)\
        .filter(url=strip_api(dhis2_conn.server_url))\
        .exists()


def strip_api(server_url):
    """
    Strips "api/" from the end of ``server_url``, if present

    >>> strip_api('https://play.dhis2.org/demo/api/')
    'https://play.dhis2.org/demo/'

    """
    if server_url.rstrip('/').endswith('api'):
        i = len(server_url.rstrip('/')) - 3
        return server_url[:i]
    return server_url


def create_conn_settings(dhis2_conn: Dhis2Connection) -> ConnectionSettings:
    """
    Creates and returns a ConnectionSettings instance for ``dhis2_conn``.
    """
    url = strip_api(dhis2_conn.server_url)
    conn_settings = ConnectionSettings(
        domain=dhis2_conn.domain,
        name=url,
        url=url,
        auth_type=BASIC_AUTH,
        username=dhis2_conn.username,
        skip_cert_verify=dhis2_conn.skip_cert_verify,
        notify_addresses_str=""
    )
    conn_settings.plaintext_password = dhis2_conn.plaintext_password
    conn_settings.save()
    return conn_settings


def link_data_set_maps(conn_settings: ConnectionSettings):
    """
    Links DataSetMap instances to their ConnectionSettings instance.
    """
    for data_set_map in get_dataset_maps(conn_settings.domain):
        if not data_set_map.connection_settings_id:
            data_set_map.connection_settings_id = conn_settings.id
            data_set_map.save()
    get_dataset_maps.clear(conn_settings.domain)
