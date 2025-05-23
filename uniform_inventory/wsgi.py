"""
WSGI config for uniform_inventory project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/wsgi/
"""

import os
from django.core.wsgi import get_wsgi_application

# Check if we should use production settings
if os.environ.get('DJANGO_ENVIRONMENT') == 'production':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'uniform_inventory.settings_prod')
else:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'uniform_inventory.settings')

application = get_wsgi_application()
