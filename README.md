# New Sport Assistant ADK Agent

## Configuration on Windows

```commandline
python -m venv .venv
```

```commandline
.venv\Scripts\activate.bat
```

## Running the Web App (API_KEY in .env file)

```commandline
adk web --port 8000
```

## Running example sessions (with InMemorySessionService and logging)

```commandline
set GOOGLE_API_KEY=your-api-key-here
python ./new_sport_agent/run_session.py
```

## Deploying to Google Cloud Run

1. Install Google Cloud SDK
2. Authenticate: gcloud auth login
3. Set project: gcloud config set project YOUR_PROJECT_ID
4. Enable APIs:
   gcloud services enable run.googleapis.com
   gcloud services enable cloudbuild.googleapis.com
5. Set environment variables

```commandline
set GCP_PROJECT_ID=your-project-id
set GCP_REGION=us-central1
set GOOGLE_API_KEY=your-gemini-api-key
```
