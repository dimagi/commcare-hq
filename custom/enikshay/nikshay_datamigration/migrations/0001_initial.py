# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='PatientDetail',
            fields=[
                ('PregId', models.CharField(max_length=255, serialize=False, primary_key=True)),
                ('Stocode', models.CharField(max_length=255, null=True)),
                ('Dtocode', models.CharField(max_length=255, null=True)),
                ('Tbunitcode', models.IntegerField(null=True)),
                ('pname', models.CharField(max_length=255, null=True)),
                ('pgender', models.CharField(max_length=255, null=True)),
                ('page', models.IntegerField(null=True)),
                ('poccupation', models.IntegerField(null=True)),
                ('paadharno', models.CharField(max_length=255, null=True)),
                ('paddress', models.CharField(max_length=255, null=True)),
                ('pmob', models.CharField(max_length=255, null=True)),
                ('plandline', models.BigIntegerField(null=True)),
                ('ptbyr', models.CharField(max_length=255, null=True)),
                ('pregdate1', models.DateField()),
                ('cname', models.CharField(max_length=255, null=True)),
                ('caddress', models.CharField(max_length=255, null=True)),
                ('cmob', models.CharField(max_length=255, null=True)),
                ('clandline', models.BigIntegerField(null=True)),
                ('cvisitedby', models.CharField(max_length=255, null=True)),
                ('cvisitedDate1', models.CharField(max_length=255, null=True)),
                ('dcpulmunory', models.CharField(max_length=255, choices=[(b'y', b'y'), (b'N', b'N')])),
                ('dcexpulmunory', models.CharField(max_length=255, null=True)),
                ('dcpulmunorydet', models.CharField(max_length=255, null=True)),
                ('dotname', models.CharField(max_length=255, null=True)),
                ('dotdesignation', models.CharField(max_length=255, null=True)),
                ('dotmob', models.CharField(max_length=255, null=True)),
                ('dotlandline', models.CharField(max_length=255, null=True)),
                ('dotpType', models.IntegerField()),
                ('dotcenter', models.CharField(max_length=255, null=True)),
                ('PHI', models.IntegerField()),
                ('dotmoname', models.CharField(max_length=255, null=True)),
                ('dotmosignDate', models.CharField(max_length=255, null=True)),
                ('atbtreatment', models.CharField(max_length=255, choices=[(b'Y', b'Y'), (b'N', b'N')])),
                ('atbduration', models.CharField(max_length=255, null=True)),
                ('atbsource', models.CharField(max_length=255, null=True, choices=[(b'G', b'G'), (b'O', b'O'), (b'P', b'P')])),
                ('atbregimen', models.CharField(max_length=255, null=True)),
                ('atbyr', models.IntegerField(null=True)),
                ('Ptype', models.IntegerField()),
                ('pcategory', models.IntegerField()),
                ('InitiationDate1', models.CharField(max_length=255, null=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
