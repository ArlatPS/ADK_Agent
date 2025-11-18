import os
import subprocess
import sys

PROJECT_ID = os.getenv('GCP_PROJECT_ID')
REGION = os.getenv('GCP_REGION')
SERVICE_NAME = 'new-sport-agent-api'
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

if not PROJECT_ID or not REGION or not GOOGLE_API_KEY:
    raise ValueError("Please set GCP_PROJECT_ID, GCP_REGION, and GOOGLE_API_KEY environment variables")

def create_dockerfile():
    """Create Dockerfile for Cloud Run deployment."""
    
    dockerfile_content = """FROM python:3.11-slim

WORKDIR /app

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY agent.py .
COPY app.py .

# Set environment variables
ENV PORT=8080
ENV PYTHONUNBUFFERED=1

# Run the application
CMD exec uvicorn app:app --host 0.0.0.0 --port $PORT
"""
    
    with open('Dockerfile', 'w') as f:
        f.write(dockerfile_content)
    
    print("✓ Created Dockerfile")

def create_requirements():
    """Create requirements.txt for deployment."""
    
    requirements = """google-adk
google-genai
fastapi
uvicorn[standard]
pydantic
"""
    
    with open('requirements.txt', 'w') as f:
        f.write(requirements)
    
    print("✓ Created requirements.txt")

def create_app():
    """Create FastAPI application wrapper."""
    
    app_content = """from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from agent import root_agent
import os
import asyncio
from typing import Optional

app = FastAPI(title="Sport Assistant Agent API")

# Initialize session service and runner
session_service = InMemorySessionService()
runner = Runner(
    agent=root_agent,
    app_name="SportAgentAPI",
    session_service=session_service
)

class ChatRequest(BaseModel):
    message: str
    user_id: str = "default"
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    session_id: str

@app.get("/")
async def root():
    return {"message": "Sport Assistant Agent API", "status": "running"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        # Generate session ID if not provided
        session_id = request.session_id or f"{request.user_id}_session"
        
        # Get or create session
        try:
            session = await session_service.create_session(
                app_name=runner.app_name,
                user_id=request.user_id,
                session_id=session_id
            )
        except:
            session = await session_service.get_session(
                app_name=runner.app_name,
                user_id=request.user_id,
                session_id=session_id
            )
        
        # Create message
        message = types.Content(
            role="user",
            parts=[types.Part(text=request.message)]
        )
        
        # Run agent and collect response
        response_text = ""
        async for event in runner.run_async(
            user_id=request.user_id,
            session_id=session.id,
            new_message=message
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text and part.text != "None":
                        response_text += part.text + "\\n"
        
        return ChatResponse(
            response=response_text.strip(),
            session_id=session.id
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
"""
    
    with open('app.py', 'w') as f:
        f.write(app_content)
    
    print("✓ Created app.py")

def create_cloudbuild():
    """Create cloudbuild.yaml for CI/CD."""
    
    cloudbuild_content = f"""steps:
  # Build the container image
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'gcr.io/{PROJECT_ID}/{SERVICE_NAME}', '.']
  
  # Push the container image to Container Registry
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'gcr.io/{PROJECT_ID}/{SERVICE_NAME}']
  
  # Deploy container image to Cloud Run
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    entrypoint: gcloud
    args:
      - 'run'
      - 'deploy'
      - '{SERVICE_NAME}'
      - '--image'
      - 'gcr.io/{PROJECT_ID}/{SERVICE_NAME}'
      - '--region'
      - '{REGION}'
      - '--platform'
      - 'managed'
      - '--allow-unauthenticated'
      - '--set-env-vars'
      - 'GOOGLE_API_KEY={GOOGLE_API_KEY}'

images:
  - 'gcr.io/{PROJECT_ID}/{SERVICE_NAME}'
"""
    
    with open('cloudbuild.yaml', 'w') as f:
        f.write(cloudbuild_content)
    
    print("✓ Created cloudbuild.yaml")

def deploy():
    """Deploy to Cloud Run."""
    
    print(f"\nDeploying {SERVICE_NAME} to Cloud Run...")
    print(f"Project: {PROJECT_ID}")
    print(f"Region: {REGION}")
    
    # Build and deploy using Cloud Build
    cmd = [
        'gcloud', 'builds', 'submit',
        '--config', 'cloudbuild.yaml',
        '--project', PROJECT_ID
    ]
    
    try:
        subprocess.run(cmd, check=True)
        print("\n✓ Deployment successful!")
        print(f"\nYour API is now available at:")
        print(f"https://{SERVICE_NAME}-<hash>-{REGION}.a.run.app")
        print("\nTest it with:")
        print(f'curl -X POST https://{SERVICE_NAME}-<hash>-{REGION}.a.run.app/chat \\')
        print('  -H "Content-Type: application/json" \\')
        print('  -d \'{"message": "I want to start running", "user_id": "user123"}\'')
        
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Deployment failed: {e}")
        return False
    
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("Sport Assistant Agent - Cloud Run Deployment")
    print("=" * 60)

    print("\nPreparing deployment files...")
    create_dockerfile()
    create_requirements()
    create_app()
    create_cloudbuild()
    
    print("\n" + "=" * 60)
    response = input("\nReady to deploy? (y/n): ")
    
    if response.lower() == 'y':
        if deploy():
            print("\n✓ Deployment complete!")
        else:
            print("\n❌ Deployment failed")
            sys.exit(1)
    else:
        print("\nDeployment cancelled. Files are ready for manual deployment.")
        print("To deploy manually, run: gcloud builds submit --config cloudbuild.yaml")
