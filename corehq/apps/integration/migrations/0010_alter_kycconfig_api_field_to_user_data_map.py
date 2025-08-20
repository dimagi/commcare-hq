from django.db import migrations
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ("integration", "0009_alter_kycconfig_connection_settings"),
    ]

    operations = [
        migrations.AlterField(
            model_name="kycconfig",
            name="api_field_to_user_data_map",
            field=jsonfield.fields.JSONField(default=dict),
        ),
    ]
