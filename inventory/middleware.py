import re
from django.conf import settings
from django.http import HttpResponseForbidden

class SecurityMiddleware:
    """Custom middleware to add additional security headers and checks"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        # Check for suspicious SQL injection patterns in GET/POST parameters
        if self._has_sql_injection(request):
            return HttpResponseForbidden("Forbidden: Potentially malicious request detected.")
            
        # Continue with the request
        response = self.get_response(request)
        
        # Add security headers if not already set by Django's middleware
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-XSS-Protection', '1; mode=block')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        
        # Add Content-Security-Policy header if not in DEBUG mode
        if not settings.DEBUG and 'Content-Security-Policy' not in response:
            csp = "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; " \
                  "style-src 'self' https://cdn.jsdelivr.net; " \
                  "img-src 'self' data:; " \
                  "font-src 'self' https://cdn.jsdelivr.net; " \
                  "frame-ancestors 'none'; " \
                  "form-action 'self';"
            response.headers.setdefault('Content-Security-Policy', csp)
            
        return response
    
    def _has_sql_injection(self, request):
        """
        Check if the request parameters contain SQL injection patterns
        """
        # Common SQL injection patterns
        sql_patterns = [
            r'(\s|;|,|\)|\"|\')(\s)*(SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|UNION|INTO|LOAD_FILE)\s+',
            r'(\/\*|\*\/|--|#|\')',
            r'(SLEEP\(\s*\d+\s*\)|BENCHMARK\(\s*\d+\s*,)',
        ]
        
        # Fields to exclude from SQL injection checks (allow special characters)
        excluded_fields = ['notes']
        
        # Combine GET and POST parameters
        all_params = dict(list(request.GET.items()) + list(request.POST.items()))
        
        # Check each parameter value
        for param, value in all_params.items():
            # Skip notes field which may contain special characters
            if param in excluded_fields:
                continue
                
            if isinstance(value, str):
                for pattern in sql_patterns:
                    if re.search(pattern, value, re.IGNORECASE):
                        return True
                        
        return False 