from django.db import migrations


class Migration(migrations.Migration):
    # This migration is now a no-op. It originally reset the `is_active` flag on
    # existing CommCareUser domain memberships, but it is no longer possible to
    # get users into that state in-product, so the one-time correction is no
    # longer needed. See https://github.com/dimagi/commcare-hq/pull/36722.

    dependencies = [
        ('users', '0082_connectidmessagingkey_unique_active_messaging_key_per_user_and_domain'),
    ]

    operations = []
