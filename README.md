# ADK_Agent

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
