from django.db import migrations, models

import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='SQLProduct',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('domain', models.CharField(max_length=255, db_index=True)),
                ('product_id', models.CharField(unique=True, max_length=100, db_index=True)),
                ('name', models.CharField(max_length=100, null=True)),
                ('is_archived', models.BooleanField(default=False)),
                ('code', models.CharField(default='', max_length=100, null=True)),
                ('description', models.TextField(default='', null=True)),
                ('category', models.CharField(default='', max_length=100, null=True)),
                ('program_id', models.CharField(default='', max_length=100, null=True)),
                ('cost', models.DecimalField(null=True, max_digits=20, decimal_places=5)),
                ('units', models.CharField(default='', max_length=100, null=True)),
                ('product_data', jsonfield.fields.JSONField(default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('last_modified', models.DateTimeField(auto_now=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
