from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

class EmailOrUsernameModelBackend(ModelBackend):
    """
    Authentication Backend that allows login with either username or email,
    with case-insensitive matching
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        
        if username is None:
            return None
            
        try:
            # Try to fetch the user by username OR email, ignoring case sensitivity
            user = UserModel.objects.filter(
                Q(username__iexact=username) | Q(email__iexact=username)
            ).first()
            
            # If we found a matching user, check their password
            if user and user.check_password(password):
                return user
                
        except UserModel.DoesNotExist:
            # No user found with this username/email
            return None
            
        # Wrong password or no user found
        return None 