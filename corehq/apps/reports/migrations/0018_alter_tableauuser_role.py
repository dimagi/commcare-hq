# Generated by Django 4.2.11 on 2024-06-21 18:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reports', '0017_alter_tableauuser_tableau_user_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tableauuser',
            name='role',
            field=models.CharField(choices=[('Explorer', 'Explorer'), ('ExplorerCanPublish', 'Explorer - Can Publish'), ('ServerAdministrator', 'Server Administrator'), ('SiteAdministratorExplorer', 'Site Administrator - Explorer'), ('SiteAdministratorCreator', 'Site Administrator - Creator'), ('Unlicensed', 'Unlicensed'), ('ReadOnly', 'Read Only'), ('Viewer', 'Viewer')], max_length=32),
        ),
    ]
