# GitHub Issues API Wrapper

## Overview

This service provides a REST API wrapper around GitHub’s Issues API for a single repository.  
It supports CRUD operations for issues and comments, secure webhook handling, and ships a full OpenAPI 3.0 contract.  
Built with FastAPI, the app includes Docker support and automated tests.

---

## Setup Instructions

### Prerequisites

- Python 3.9 or higher  
- Docker (optional)  
- GitHub Personal Access Token with `Issues: Read and Write` permission  

### Environment Variables

Create a `.env` file from `.env.example` and fill in your secrets:

GITHUB_TOKEN=your_github_personal_access_token
GITHUB_OWNER=your_github_username_or_org
GITHUB_REPO=your_repository_name
WEBHOOK_SECRET=your_webhook_secret
PORT=8000

---

### Create and Activate Python Virtual Environment

1. Create a virtual environment (run once):

python -m venv venv

2. Activate the virtual environment:

- On **Windows (Command Prompt):**

venv\Scripts\activate.bat

- On **Windows (PowerShell):**

.\venv\Scripts\Activate.ps1

- On **macOS/Linux (bash):**

source venv/bin/activate

3. After activation, your prompt should show `(venv)`, indicating the environment is active.

---

### Install Dependencies

pip install -r requirements.txt

---

### Run the App Locally

uvicorn main:app --reload --port=8000

Access the API docs at [http://localhost:8000/docs](http://localhost:8000/docs).

---

### Running with Docker

1. Build the Docker image:

docker build -t github-issues-wrapper .


2. Run the container with environment variables:

docker run --rm -p 8000:8000 --env-file .env github-issues-wrapper

---

## API Usage Examples

- Create an issue:

curl -X POST "http://localhost:8000/issues" -H "Content-Type: application/json" -d '{"title":"Bug found","body":"Steps to reproduce the bug","labels":["bug"]}'

- List issues:

curl "http://localhost:8000/issues?state=open&per_page=20"

- Get a single issue:

curl "http://localhost:8000/issues/1"

- Update an issue:

curl -X PATCH "http://localhost:8000/issues/1" -H "Content-Type: application/json" -d '{"state":"closed"}'

- Add a comment:

curl -X POST "http://localhost:8000/issues/1/comments" -H "Content-Type: application/json" -d '{"body":"Thanks for the update!"}'

---

## Webhook Setup

- In your GitHub repository, go to **Settings > Webhooks > Add webhook**.  
- Set the **Payload URL** to your service webhook endpoint `http://<your-server>/webhook`.  
- Choose **Content type** as `application/json`.  
- Set the **Secret** to the same as `WEBHOOK_SECRET`.  
- Select events: **Issues**, **Issue comment**, and **Ping**.  
- Save the webhook.

---

## Testing

All tests are located in the `tests/` folder.  
Run tests using:

pytest

---

## Design Notes

- Security: GitHub token and webhook secret are environment variables only.  
- Webhook verification uses HMAC SHA-256 signature checks.  
- Idempotent webhook processing via delivery IDs.  
- Rate limits from GitHub forwarded via headers.  

---

## License

MIT License
