"""
FastAPI application fixture for testing the FastAPIParser.

Defines a FastAPI app with APIRouters, path/query parameters,
dependency injection for authentication, and router inclusion
to exercise all detection paths in the parser.
"""

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.security import OAuth2PasswordBearer

from .routers import items, users

# --- Auth dependency ---
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


async def get_current_user(token: str = Depends(oauth2_scheme)):
    """Validate token and return current user."""
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {"username": "testuser"}


# --- Application ---
app = FastAPI(title="Test API", version="1.0.0")


# --- App-level routes ---
@app.get("/")
async def root():
    """Health check / root endpoint."""
    return {"status": "ok"}


@app.get("/health", tags=["monitoring"])
async def health_check():
    """Detailed health check."""
    return {"status": "healthy", "version": "1.0.0"}


@app.post("/auth/login", tags=["auth"])
async def login(username: str, password: str):
    """Authenticate user and return token."""
    return {"access_token": "fake-token", "token_type": "bearer"}


@app.get("/me", tags=["auth"])
async def get_me(current_user: dict = Depends(get_current_user)):
    """Get current authenticated user profile."""
    return current_user


# --- Include routers ---
app.include_router(items.router, prefix="/api/v1", tags=["items"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])


# --- Inline router for admin ---
from fastapi import APIRouter

admin_router = APIRouter(prefix="/admin", tags=["admin"])


@admin_router.get("/dashboard")
async def admin_dashboard(current_user: dict = Depends(get_current_user)):
    """Admin dashboard endpoint."""
    return {"dashboard": "data"}


@admin_router.delete("/users/{user_id}")
async def admin_delete_user(user_id: int, current_user: dict = Depends(get_current_user)):
    """Delete a user (admin only)."""
    return {"deleted": user_id}


app.include_router(admin_router)
