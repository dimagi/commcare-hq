from django.db import migrations
from django.db.migrations import RunPython

from corehq.util.django_migrations import skip_on_fresh_install
from corehq.motech.const import ALGO_AES_CBC
from corehq.motech.utils import (
    reencrypt_ecb_to_cbc_mode,
    reencrypt_cbc_to_ecb_mode,
    AesEcbDecryptionError
)


@skip_on_fresh_install
def reencrypt_api_tokens(apps, schema_editor):
    TransifexOrganization = apps.get_model('translations', 'TransifexOrganization')

    transifex_orgs_to_update = TransifexOrganization.objects.exclude(
        api_token__startswith=f'${ALGO_AES_CBC}$'
    ).exclude(api_token=None).exclude(api_token='')

    for org in transifex_orgs_to_update:
        try:
            org.api_token = reencrypt_ecb_to_cbc_mode(org.api_token)
        except AesEcbDecryptionError:
            org.api_token = ''
        org.save()


def reversion_api_tokens(apps, schema_editor):
    TransifexOrganization = apps.get_model('translations', 'TransifexOrganization')

    transifex_orgs_to_update = TransifexOrganization.objects.filter(
        api_token__startswith=f'${ALGO_AES_CBC}$'
    )

    for org in transifex_orgs_to_update:
        org.api_token = reencrypt_cbc_to_ecb_mode(org.api_token,
                                                f'${ALGO_AES_CBC}$')
        org.save()


class Migration(migrations.Migration):

    dependencies = [
        ('translations', '0009_auto_20200924_1753'),
    ]

    operations = [
        RunPython(reencrypt_api_tokens, reverse_code=reversion_api_tokens),
    ]
