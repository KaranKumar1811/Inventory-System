# Uniform Inventory System

A comprehensive inventory management system for tracking employee uniforms.

## Features

- Employee management with uniform tracking
- Transaction history with detailed reporting
- PDF generation for employee records
- Secure authentication and authorization
- Dashboard with data visualization

## Deploying to Replit

This application can be deployed to Replit by following these steps:

1. Create a new Repl on Replit.com
2. Select "Import from GitHub" 
3. Enter the GitHub repository URL
4. Replit will automatically set up the environment

### Running the Application

The application should start automatically when the Repl is created. If it doesn't:

1. In the Replit shell, run:
   ```
   bash replit_deploy.sh
   ```

2. This script will:
   - Install dependencies
   - Run database migrations
   - Collect static files
   - Create a superuser account
   - Start the Django server

### Important Notes

- The application will be accessible at the URL provided by Replit
- Database will be stored within the Repl
- Security has been configured for the Replit environment
- Login rate limiting is enabled for security

## Local Development

1. Clone the repository
2. Create a virtual environment: `python -m venv env`
3. Activate the environment: `source env/bin/activate` (Unix) or `env\Scripts\activate` (Windows)
4. Install dependencies: `pip install -r requirements.txt`
5. Run migrations: `python manage.py migrate`
6. Start the server: `python manage.py runserver`

## Security Features

For details about security measures implemented in this application, see SECURITY.md.
