from django.db import migrations
from django.contrib.auth.hashers import make_password

def create_superuser(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    
    # Check if the superuser already exists
    if not User.objects.filter(username='admin').exists():
        User.objects.create(
            username='admin',
            email='admin@example.com',
            password=make_password('Admin123!'),
            is_staff=True,
            is_active=True,
            is_superuser=True
        )
        print("Created hardcoded superuser 'admin'")

def reverse_migration(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    User.objects.filter(username='admin', email='admin@example.com').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0024_alter_equipmentitem_options_and_more'),
    ]

    operations = [
        migrations.RunPython(create_superuser, reverse_migration),
    ] 