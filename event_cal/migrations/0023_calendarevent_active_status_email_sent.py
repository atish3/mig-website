# -*- coding: utf-8 -*-
# Generated by Django 1.10.2 on 2016-12-06 01:56
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('event_cal', '0022_auto_20161020_1929'),
    ]

    operations = [
        migrations.AddField(
            model_name='calendarevent',
            name='active_status_email_sent',
            field=models.BooleanField(default=False),
        ),
    ]
