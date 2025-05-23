# Generated by Django 5.1.6 on 2025-03-27 15:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0021_uniformsize_uniformtype_uniform_uniform_type'),
    ]

    operations = [
        migrations.CreateModel(
            name='SiteLocation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('address', models.CharField(blank=True, max_length=255, null=True)),
                ('description', models.TextField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Site Location',
                'verbose_name_plural': 'Site Locations',
                'ordering': ['name'],
            },
        ),
    ]
