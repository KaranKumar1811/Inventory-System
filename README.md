# Uniform Inventory System

A comprehensive inventory management system for tracking employee uniforms.

## Features

- Employee management with uniform tracking
- Transaction history with detailed reporting
- PDF generation for employee records
- Secure authentication and authorization
- Dashboard with data visualization

## Deploying to Railway

This application can be deployed to Railway.app by following these steps:

1. Create an account on [Railway.app](https://railway.app/)
2. Install the Railway CLI: `npm i -g @railway/cli`
3. Login to Railway: `railway login`
4. Initialize your project: `railway init`
5. Create a PostgreSQL database: `railway add`
6. Deploy your application: `railway up`

### Railway Environment Variables

Configure the following environment variables in your Railway project settings:

- `DJANGO_SECRET_KEY`: Generate a secure key (python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')
- `DJANGO_DEBUG`: Set to "False" for production
- `DJANGO_ALLOWED_HOSTS`: Your Railway domain (automatically added by settings.py)
- `DATABASE_URL`: Automatically provided by Railway

### First-time Setup

After deploying, you'll need to create a superuser to access the admin panel:

```
railway run python manage.py createsuperuser
```

## Local Development

1. Clone the repository
2. Create a virtual environment: `python -m venv env`
3. Activate the environment: `source env/bin/activate` (Unix) or `env\Scripts\activate` (Windows)
4. Install dependencies: `pip install -r requirements.txt`
5. Run migrations: `python manage.py migrate`
6. Start the server: `python manage.py runserver`

## Security Features

For details about security measures implemented in this application, see SECURITY.md.
