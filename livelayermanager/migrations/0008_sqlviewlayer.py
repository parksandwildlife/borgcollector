# -*- coding: utf-8 -*-
# Generated by Django 1.9.7 on 2017-06-02 06:31
from __future__ import unicode_literals

import borg_utils.resource_status
import borg_utils.transaction
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('livelayermanager', '0007_layer_kmi_bbox'),
    ]

    operations = [
        migrations.CreateModel(
            name='SqlViewLayer',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=256, unique=True)),
                ('viewsql', models.TextField()),
                ('spatial_type', models.IntegerField(default=1, editable=False)),
                ('sql', models.TextField(editable=False, null=True)),
                ('crs', models.CharField(blank=True, editable=False, max_length=64, null=True)),
                ('bbox', models.CharField(editable=False, max_length=128, null=True)),
                ('kmi_bbox', models.CharField(blank=True, max_length=128, null=True)),
                ('geoserver_setting', models.TextField(blank=True, editable=False, null=True)),
                ('status', models.CharField(choices=[(b'New', b'New'), (b'Updated', b'Updated'), (b'Published', b'Published'), (b'CascadePublished', b'CascadePublished'), (b'Unpublished', b'Unpublished'), (b'CascadeUnpublished', b'CascadeUnpublished')], editable=False, max_length=32)),
                ('last_publish_time', models.DateTimeField(editable=False, null=True)),
                ('last_unpublish_time', models.DateTimeField(editable=False, null=True)),
                ('last_refresh_time', models.DateTimeField(editable=False)),
                ('last_modify_time', models.DateTimeField(editable=False, null=True)),
                ('create_time', models.DateTimeField(auto_now_add=True)),
                ('datasource', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='livelayermanager.Datasource')),
            ],
            options={
                'ordering': ('datasource', 'name'),
            },
            bases=(models.Model, borg_utils.resource_status.ResourceStatusMixin, borg_utils.transaction.TransactionMixin),
        ),
    ]