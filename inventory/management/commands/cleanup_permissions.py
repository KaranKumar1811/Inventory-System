from django.core.management.base import BaseCommand
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType

class Command(BaseCommand):
    help = 'Cleans up obsolete permissions for models that no longer exist'

    def handle(self, *args, **options):
        # List of obsolete models
        obsolete_models = [
            'uniformassignment',
            'uniformsignoff',
            'uniformsignoffitem',
        ]
        
        # Get content types for obsolete models
        obsolete_content_types = ContentType.objects.filter(
            app_label='inventory',
            model__in=obsolete_models
        )
        
        # Get permissions for these content types
        obsolete_permissions = Permission.objects.filter(
            content_type__in=obsolete_content_types
        )
        
        # Count and list permissions to be deleted
        count = obsolete_permissions.count()
        
        if count > 0:
            self.stdout.write(self.style.WARNING(f'Found {count} obsolete permissions to delete:'))
            for perm in obsolete_permissions:
                self.stdout.write(f'  - {perm.codename} ({perm.content_type.app_label}.{perm.content_type.model})')
            
            # Delete the permissions
            obsolete_permissions.delete()
            self.stdout.write(self.style.SUCCESS(f'Successfully deleted {count} obsolete permissions'))
        else:
            self.stdout.write(self.style.SUCCESS('No obsolete permissions found')) 