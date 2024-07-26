from django.db import migrations

from corehq.apps.users.util import user_location_data
from corehq.apps.users.models import CommCareUser
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def remove_keys_from_data(apps, schema_editor):
    SQLUserData = apps.get_model('users', 'SQLUserData')

    for user_data in SQLUserData.objects.all():
        data = user_data.data
        keys_to_remove = ['commcare_location_id', 'commcare_location_ids', 'commcare_primary_case_sharing_id']

        modified = False
        for key in keys_to_remove:
            if key in data:
                del data[key]
                modified = True

        if modified:
            user_data.data = data
            user_data.save()


def revert_keys_in_data(apps, schema_editor):
    SQLUserData = apps.get_model('users', 'SQLUserData')
    CommCareUserCouch = CommCareUser.get_db()

    for user_data in SQLUserData.objects.all():
        user_id = user_data.user_id

        commcare_user = CommCareUserCouch.get(user_id)

        data = user_data.data
        location_id = commcare_user.get('location_id')
        assigned_location_ids = commcare_user.get('assigned_location_ids', [])

        if location_id:
            data['commcare_location_id'] = location_id
            data['commcare_primary_case_sharing_id'] = location_id
        if assigned_location_ids:
            data['commcare_location_ids'] = user_location_data(assigned_location_ids)

        user_data.data = data
        user_data.save()


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0071_rm_user_data'),
    ]

    operations = [
        migrations.RunPython(remove_keys_from_data, revert_keys_in_data),
    ]
