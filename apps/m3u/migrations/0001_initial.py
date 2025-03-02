# Generated by Django 5.1.6 on 2025-03-02 13:52

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ServerGroup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Unique name for this server group.', max_length=100, unique=True)),
            ],
        ),
        migrations.CreateModel(
            name='M3UAccount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Unique name for this M3U account', max_length=255, unique=True)),
                ('server_url', models.URLField(blank=True, help_text='The base URL of the M3U server (optional if a file is uploaded)', null=True)),
                ('uploaded_file', models.FileField(blank=True, null=True, upload_to='m3u_uploads/')),
                ('max_streams', models.PositiveIntegerField(default=0, help_text='Maximum number of concurrent streams (0 for unlimited)')),
                ('is_active', models.BooleanField(default=True, help_text='Set to false to deactivate this M3U account')),
                ('created_at', models.DateTimeField(auto_now_add=True, help_text='Time when this account was created')),
                ('updated_at', models.DateTimeField(auto_now=True, help_text='Time when this account was last updated')),
                ('user_agent', models.ForeignKey(blank=True, help_text='The User-Agent associated with this M3U account.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='m3u_accounts', to='core.useragent')),
                ('server_group', models.ForeignKey(blank=True, help_text='The server group this M3U account belongs to', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='m3u_accounts', to='m3u.servergroup')),
            ],
        ),
        migrations.CreateModel(
            name='M3UFilter',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('filter_type', models.CharField(choices=[('group', 'Group Title'), ('name', 'Stream Name')], default='group', help_text='Filter based on either group title or stream name.', max_length=50)),
                ('regex_pattern', models.CharField(help_text='A regex pattern to match streams or groups.', max_length=200)),
                ('exclude', models.BooleanField(default=True, help_text='If True, matching items are excluded; if False, only matches are included.')),
                ('m3u_account', models.ForeignKey(help_text='The M3U account this filter is applied to.', on_delete=django.db.models.deletion.CASCADE, related_name='filters', to='m3u.m3uaccount')),
            ],
        ),
        migrations.CreateModel(
            name='M3UAccountProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Name for the M3U account profile', max_length=255)),
                ('is_default', models.BooleanField(default=False, help_text='Set to false to deactivate this profile')),
                ('max_streams', models.PositiveIntegerField(default=0, help_text='Maximum number of concurrent streams (0 for unlimited)')),
                ('is_active', models.BooleanField(default=True, help_text='Set to false to deactivate this profile')),
                ('search_pattern', models.CharField(max_length=255)),
                ('replace_pattern', models.CharField(max_length=255)),
                ('current_viewers', models.PositiveIntegerField(default=0)),
                ('m3u_account', models.ForeignKey(help_text='The M3U account this profile belongs to.', on_delete=django.db.models.deletion.CASCADE, related_name='profiles', to='m3u.m3uaccount')),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=('m3u_account', 'name'), name='unique_account_profile_name')],
            },
        ),
    ]
