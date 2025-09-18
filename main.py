import os
import hmac
import hashlib
from fastapi import FastAPI, Request, Header, HTTPException, status, Response
from pydantic import BaseModel, Field
from typing import Optional, List
import httpx
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_OWNER = os.getenv("GITHUB_OWNER")
GITHUB_REPO = os.getenv("GITHUB_REPO")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
PORT = int(os.getenv("PORT", "8000"))

app = FastAPI()

HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
}

# Models
class IssueCreate(BaseModel):
    title: str = Field(..., min_length=1)
    body: Optional[str] = None
    labels: Optional[List[str]] = []

class IssueUpdate(BaseModel):
    title: Optional[str]
    body: Optional[str]
    state: Optional[str]

class CommentCreate(BaseModel):
    body: str = Field(..., min_length=1)

# Utility to extract label names
def extract_labels(issue_data):
    return [label["name"] for label in issue_data.get("labels", [])]

# POST /issues - create issue
@app.post("/issues", status_code=201)
async def create_issue(issue: IssueCreate, response: Response):
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/issues"
    payload = {
        "title": issue.title,
        "body": issue.body,
        "labels": issue.labels or [],
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(url, headers=HEADERS, json=payload)
    if r.status_code == 201:
        data = r.json()
        response.headers["Location"] = f"/issues/{data['number']}"
        return {
            "number": data["number"],
            "title": data["title"],
            "body": data.get("body"),
            "state": data["state"],
            "labels": extract_labels(data),
            "html_url": data["html_url"],
            "created_at": data["created_at"],
            "updated_at": data["updated_at"],
        }
    elif r.status_code == 401:
        raise HTTPException(status_code=401, detail="Unauthorized")
    else:
        raise HTTPException(status_code=400, detail=r.text)

# GET /issues - list issues with filters
@app.get("/issues")
async def list_issues(state: str = "open", labels: Optional[str] = None, page: int = 1, per_page: int = 30, response: Response = None):
    params = {"state": state, "page": page, "per_page": per_page}
    if labels:
        params["labels"] = labels
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/issues"
    async with httpx.AsyncClient() as client:
        r = await client.get(url, headers=HEADERS, params=params)
    if r.status_code == 200:
        for h in ["Link", "X-RateLimit-Remaining", "X-RateLimit-Reset"]:
            if h in r.headers:
                response.headers[h] = r.headers[h]
        issues = []
        for i in r.json():
            issues.append({
                "number": i["number"],
                "title": i["title"],
                "state": i["state"],
                "labels": extract_labels(i),
                "html_url": i["html_url"],
                "created_at": i["created_at"],
                "updated_at": i["updated_at"],
            })
        return issues
    else:
        raise HTTPException(status_code=r.status_code, detail=r.text)

# GET /issues/{number} - get a specific issue
@app.get("/issues/{number}")
async def get_issue(number: int):
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/issues/{number}"
    async with httpx.AsyncClient() as client:
        r = await client.get(url, headers=HEADERS)
    if r.status_code == 200:
        data = r.json()
        return {
            "number": data["number"],
            "title": data["title"],
            "body": data.get("body"),
            "state": data["state"],
            "labels": extract_labels(data),
            "html_url": data["html_url"],
            "created_at": data["created_at"],
            "updated_at": data["updated_at"],
        }
    elif r.status_code == 404:
        raise HTTPException(status_code=404, detail="Issue not found")
    else:
        raise HTTPException(status_code=r.status_code, detail=r.text)

# PATCH /issues/{number} - update issue info
@app.patch("/issues/{number}")
async def update_issue(number: int, issue: IssueUpdate):
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/issues/{number}"
    update_payload = issue.dict(exclude_unset=True)
    if "state" in update_payload and update_payload["state"] not in ["open", "closed"]:
        raise HTTPException(status_code=400, detail="state must be 'open' or 'closed'")
    async with httpx.AsyncClient() as client:
        r = await client.patch(url, headers=HEADERS, json=update_payload)
    if r.status_code == 200:
        return r.json()
    elif r.status_code == 404:
        raise HTTPException(status_code=404, detail="Issue not found")
    else:
        raise HTTPException(status_code=r.status_code, detail=r.text)

# POST /issues/{number}/comments - comment on issue
@app.post("/issues/{number}/comments", status_code=201)
async def add_comment(number: int, comment: CommentCreate):
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/issues/{number}/comments"
    async with httpx.AsyncClient() as client:
        r = await client.post(url, headers=HEADERS, json={"body": comment.body})
    if r.status_code == 201:
        data = r.json()
        return {
            "id": data["id"],
            "body": data["body"],
            "user": data["user"]["login"],
            "created_at": data["created_at"],
            "html_url": data["html_url"],
        }
    elif r.status_code == 404:
        raise HTTPException(status_code=404, detail="Issue not found")
    else:
        raise HTTPException(status_code=r.status_code, detail=r.text)

# Webhook event storage and verification
events_store = []

def verify_signature(signature: str, body: bytes) -> bool:
    if not signature:
        return False
    computed = hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={computed}", signature)

@app.post("/webhook", status_code=204)
async def webhook_handler(
    request: Request,
    x_hub_signature_256: str = Header(None),
    x_github_event: str = Header(None),
    x_github_delivery: str = Header(None),
):
    body = await request.body()
    if not verify_signature(x_hub_signature_256, body):
        raise HTTPException(status_code=401, detail="Invalid signature")

    if x_github_event not in ["issues", "issue_comment", "ping"]:
        raise HTTPException(status_code=400, detail="Unsupported event")

    payload = await request.json()
    if any(e["id"] == x_github_delivery for e in events_store):
        return Response(status_code=204)  # Deduplicate

    event_record = {
        "id": x_github_delivery,
        "event": x_github_event,
        "action": payload.get("action"),
        "issue_number": payload.get("issue", {}).get("number"),
        "timestamp": payload.get("repository", {}).get("updated_at"),
    }
    events_store.append(event_record)
    print(f"Stored webhook event: {event_record}")
    return Response(status_code=204)

@app.get("/events")
async def get_events(limit: int = 10):
    return events_store[-limit:]

@app.get("/healthz")
def health():
    return {"status": "ok"}
