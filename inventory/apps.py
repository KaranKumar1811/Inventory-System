from django.apps import AppConfig


class InventoryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'inventory'
    
    def ready(self):
        """
        Disable django-axes signal handler for successful logins to 
        avoid the session_hash error.
        """
        from django.contrib.auth.signals import user_logged_in
        from axes.signals import handle_user_logged_in
        
        # Disconnect the axes signal handler to prevent it from running on successful login
        user_logged_in.disconnect(handle_user_logged_in)
