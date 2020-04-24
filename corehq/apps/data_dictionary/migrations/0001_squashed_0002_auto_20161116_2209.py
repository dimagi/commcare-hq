from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='CaseType',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('domain', models.CharField(max_length=255)),
                ('name', models.CharField(max_length=255)),
            ],
        ),
        migrations.CreateModel(
            name='CaseProperty',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('case_type', models.ForeignKey(to='data_dictionary.CaseType', on_delete=models.CASCADE)),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField()),
                ('deprecated', models.BooleanField(default=False)),
                ('type', models.CharField(default='', max_length=20, choices=[('Date', 'Date'), ('Plain', 'Plain'), ('Number', 'Number'), ('Select', 'Select'), ('Integer', 'Integer'), ('', 'No Type Currently Selected')])),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='caseproperty',
            unique_together=set([('case_type', 'name')]),
        ),
        migrations.AlterUniqueTogether(
            name='casetype',
            unique_together=set([('domain', 'name')]),
        ),
        migrations.AlterField(
            model_name='caseproperty',
            name='case_type',
            field=models.ForeignKey(related_query_name='property', related_name='properties', to='data_dictionary.CaseType', on_delete=models.CASCADE),
        ),
    ]
