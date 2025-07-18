from django.db import migrations

from corehq.apps.es import UserES, filters
from corehq.apps.users.models import CommCareUser
from corehq.util.couch import DocUpdate, iter_update
from corehq.util.log import with_progress_bar


def affected_ids():
    return UserES().mobile_users().nested(
        'user_domain_memberships',
        filters.term('user_domain_memberships.is_active', False),
    ).scroll_ids()


def fix_user(user_doc):
    if user_doc['domain_membership'].get('is_active', True) is False:
        user_doc['domain_membership']['is_active'] = True
        return DocUpdate(user_doc)


def reset_is_active(apps, schema_editor):
    iter_update(
        CommCareUser.get_db(),
        fix_user,
        with_progress_bar(list(affected_ids())),
    )


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0082_connectidmessagingkey_unique_active_messaging_key_per_user_and_domain'),
    ]

    operations = [
        migrations.RunPython(reset_is_active),
    ]
