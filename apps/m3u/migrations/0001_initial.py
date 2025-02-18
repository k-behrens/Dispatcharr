# Generated by Django 4.2.2 on 2025-02-18 16:34

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
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
            ],
        ),
        migrations.CreateModel(
            name='ServerGroup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Unique name for this server group.', max_length=100, unique=True)),
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
        migrations.AddField(
            model_name='m3uaccount',
            name='server_group',
            field=models.ForeignKey(blank=True, help_text='The server group this M3U account belongs to', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='m3u_accounts', to='m3u.servergroup'),
        ),
    ]
