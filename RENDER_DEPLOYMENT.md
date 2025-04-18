# GlassRain Deployment Guide for Render

This document provides instructions for deploying the GlassRain application on Render.

## Deployment Steps

1. Create a new Web Service on Render
2. Connect your GitHub repository
3. Configure the following settings:
   - Name: `glassrain`
   - Root Directory: Leave empty (if GlassRain is at the root of the repository)
   - Environment: `Python 3`
   - Build Command: `pip install -r glassrain_production/requirements.txt`
   - Start Command: `cd glassrain_production && gunicorn 'wsgi:app' --bind '0.0.0.0:$PORT' --log-file -`
4. Add the required environment variables (see below)
5. Click "Create Web Service"

## Required Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `FLASK_SECRET_KEY` | Secret key for Flask session security | `generate-a-secure-random-key` |
| `OPENAI_API_KEY` | API key for OpenAI's GPT models | `sk-...` |
| `MAPBOX_API_KEY` | API key for Mapbox geocoding and maps | `pk-...` |
| `OPENWEATHER_API_KEY` | API key for OpenWeather data (optional) | `...` |
| `WEATHERAPI_KEY` | API key for WeatherAPI data (optional) | `...` |

## Database Configuration

GlassRain requires a PostgreSQL database. On Render:

1. Create a new PostgreSQL database service
2. Render will automatically create a `DATABASE_URL` environment variable when you link the database to your web service
3. The application will use this environment variable to connect to the database

## Verifying Deployment

After deploying, you can verify the API status by accessing:

- `https://your-app-name.onrender.com/api/status`

The homepage should be available at:

- `https://your-app-name.onrender.com/`

## Monitoring and Logs

Render provides built-in logging and monitoring. You can access logs from the Render dashboard to troubleshoot any issues.

## Security Considerations

1. Ensure all API keys are kept confidential
2. Do not include sensitive credentials in the repository
3. Use Render's environment variables for all sensitive information
4. Consider enabling Render's automatic TLS certificates for HTTPS

## Scaling

If needed, you can easily scale your application on Render by:

1. Increasing the number of instances
2. Upgrading to a higher performance plan
3. Enabling auto-scaling options if available