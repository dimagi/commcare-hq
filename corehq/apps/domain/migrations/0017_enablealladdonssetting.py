from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("domain", "0016_rename_superuserprojectentryrecord_domain_username_domain_supe_domain_c3d32e_idx"),
    ]

    operations = [
        migrations.CreateModel(
            name="EnableAllAddOnsSetting",
            fields=[
                ("domain", models.CharField(
                    max_length=255,
                    primary_key=True,
                    serialize=False,
                )),
                ("enabled", models.BooleanField(default=False)),
            ],
        ),
    ]
