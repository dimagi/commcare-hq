from django.db import migrations

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


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0071_rm_user_data'),
    ]

    operations = [
        migrations.RunPython(remove_keys_from_data),
    ]
