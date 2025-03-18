# Security Guide for Uniform Inventory System

This document outlines the security features implemented in the Uniform Inventory System and provides guidance on proper configuration for production environments.

## Security Features

The following security features have been implemented:

1. **Environment-based Configuration**: Secret keys and other sensitive information are stored in environment variables.
2. **Login Rate Limiting**: Protection against brute force attacks with django-axes.
3. **HTTPS Enforcement**: Production settings enforce HTTPS connections.
4. **Advanced Password Hashing**: Argon2 password hashing for stronger security.
5. **Content Security Policy**: Protection against XSS attacks.
6. **Cross-Origin Resource Sharing**: Strict CORS policy to prevent unauthorized access.
7. **SQL Injection Protection**: Custom middleware for additional SQL injection detection.
8. **Security Headers**: HTTP security headers to protect against various attacks.
9. **Session Security**: Sessions are secured with httponly and secure flags, with reasonable timeout.

## Production Setup

Follow these steps to properly secure your production environment:

1. **Create a .env file** based on the .env.example template with secure values.
2. **Generate a new Django Secret Key**:
   ```
   python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
   ```
3. **Install required packages**:
   ```
   pip install -r requirements.txt
   ```
4. **Set Production Environment**:
   ```
   export DJANGO_ENVIRONMENT=production
   ```
5. **Configure HTTPS** with a valid SSL certificate.
6. **Configure Allowed Hosts** in your .env file:
   ```
   DJANGO_ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
   ```
7. **Consider using PostgreSQL** instead of SQLite for production:
   ```
   DATABASE_URL=postgres://user:password@localhost:5432/uniforms
   ```
8. **Create a logs directory**:
   ```
   mkdir -p logs
   ```
9. **Collect static files**:
   ```
   python manage.py collectstatic
   ```
10. **Use a production-grade WSGI server** like Gunicorn:
   ```
   gunicorn uniform_inventory.wsgi
   ```

## Security Best Practices

1. **Regular Updates**: Keep Django and all dependencies updated to patch security vulnerabilities.
2. **Regular Backups**: Implement automated database backups.
3. **User Access Control**: Regularly audit user accounts and permissions.
4. **Monitoring**: Set up monitoring for suspicious activity.
5. **Security Reviews**: Conduct periodic security reviews of the application.

## Additional Security Measures

For critical deployments, consider:

1. **Two-Factor Authentication**: Implement 2FA for admin users.
2. **Web Application Firewall**: Configure a WAF to block common attacks.
3. **Security Penetration Testing**: Regular security testing.
4. **Database Encryption**: Encrypt sensitive data at rest.

## Reporting Security Issues

If you discover any security vulnerabilities, please report them to the system administrator immediately. 