#!/bin/bash

# Install dependencies
pip install -r requirements.txt

# Create logs directory if it doesn't exist
mkdir -p logs

# Apply database migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Create a superuser if one doesn't exist
# You'll be prompted to enter credentials
echo "Creating a superuser account. If one already exists, press Ctrl+C to skip this step."
python manage.py createsuperuser

# Run the server 
python manage.py runserver 0.0.0.0:3000 