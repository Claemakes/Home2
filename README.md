# GlassRain Property Intelligence Platform

An advanced spatial intelligence platform revolutionizing property management through cutting-edge AI and interactive 3D visualization technologies, providing comprehensive solutions for homeowners, design professionals, and property enthusiasts.

## Deployment Instructions for Render

### Step 1: Create a Render Account & Project
1. Sign up at [render.com](https://render.com/) or log in
2. Click "New" and select "Web Service"
3. Connect your Git repository where GlassRain code is stored
4. Select the repository and branch

### Step 2: Configure Web Service Settings
1. Fill in these details:
   - **Name**: `glassrain` (or your preferred name)
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn wsgi:app`
   - **Plan**: Choose appropriate plan (starts with free tier)

2. Expand "Advanced" settings and configure:
   - Set Python version to 3.9 or newer
   - Check "Auto-Deploy" if desired

### Step 3: Create PostgreSQL Database
1. Click "New" in the Render dashboard and select "PostgreSQL"
2. Configure the database:
   - **Name**: `glassrain-db` (or your preferred name)
   - **Database**: `glassrain` (default is fine)
   - **User**: Leave as default
   - **Plan**: Choose appropriate plan
3. Click "Create Database"
4. Take note of the connection details shown after creation

### Step 4: Configure Environment Variables
1. Return to your web service dashboard
2. Go to "Environment" tab
3. Add the following environment variables:

```
DATABASE_URL=postgres://user:password@host:port/database
MAPBOX_API_KEY=your_mapbox_api_key
OPENAI_API_KEY=your_openai_api_key
WEATHERAPI_KEY=your_weatherapi_key
FLASK_ENV=production
```

### Step 5: Deploy and Initialize
1. Click "Deploy" and wait for the service to build and deploy
2. Watch the logs for any errors during deployment
3. On first run, the database will be initialized automatically by the `setup_database` function in `glassrain_unified.py`

## Required API Keys

- **Mapbox API Key**: For address autocomplete and 3D map visualization [Get from Mapbox](https://account.mapbox.com/)
- **OpenAI API Key**: For AI-powered design assistant and DIY helper [Get from OpenAI](https://platform.openai.com/account/api-keys)
- **Weather API Key**: For property weather data integration [Get from WeatherAPI](https://www.weatherapi.com/my/)

## Features

- **Interactive 3D Property Visualization**: View property in detailed 3D
- **AI Design Assistant (Elevate tab)**: Get AI-powered design recommendations
- **DIY Assistant**: AI-guided home improvement assistance
- **Services Marketplace**: Connect with qualified contractors
- **Weather Integration**: Real-time weather data for properties
- **Energy Efficiency Analysis**: Track property energy performance