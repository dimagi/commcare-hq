from django.db import migrations
from django.db.migrations import RunPython

from corehq.util.django_migrations import skip_on_fresh_install
from corehq.motech.const import ALGO_AES, ALGO_AES_CBC
from corehq.motech.utils import (
    reencrypt_ecb_to_cbc_mode,
    reencrypt_cbc_to_ecb_mode,
    b64_aes_cbc_encrypt,
)


@skip_on_fresh_install
def reencrypt_api_keys(apps, schema_editor):
    GeoConfig = apps.get_model('geospatial', 'GeoConfig')

    geo_configs_to_update = GeoConfig.objects.exclude(
        api_token__startswith=f'${ALGO_AES_CBC}$'
    ).exclude(api_token=None)

    for config in geo_configs_to_update:
        if config.api_token.startswith(f'${ALGO_AES}$'):
            config.api_token = reencrypt_ecb_to_cbc_mode(config.api_token,
                                                         f'${ALGO_AES}$')
        else:
            ciphertext = b64_aes_cbc_encrypt(config.api_token)
            config.api_token = f'${ALGO_AES_CBC}${ciphertext}'
        config.save()


def reversion_api_keys(apps, schema_editor):
    GeoConfig = apps.get_model('geospatial', 'GeoConfig')

    geo_configs_to_revert = GeoConfig.objects.filter(
        api_token__startswith=f'${ALGO_AES_CBC}$'
    )

    for config in geo_configs_to_revert:
        config.api_token = reencrypt_cbc_to_ecb_mode(config.api_token,
                                                    f'${ALGO_AES_CBC}$')
        config.save()


class Migration(migrations.Migration):

    dependencies = [
        ('geospatial', '0008_geoconfig_flag_assigned_cases'),
    ]

    operations = [
        RunPython(reencrypt_api_keys, reverse_code=reversion_api_keys),
    ]
