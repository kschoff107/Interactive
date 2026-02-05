# Windows Setup and Database Configuration Fixes

**Date:** February 5, 2026
**Issue:** Application startup failures and project creation errors on Windows
**Status:** ✓ Resolved

## Summary

Fixed critical issues preventing the Code Visualizer app from running properly on Windows, including database configuration errors and Flask reloader compatibility problems.

---

## Issues Encountered

### 1. Database Configuration Error
**Error Message:** `ERROR: DATABASE_URL is not SQLite format`

**Root Cause:**
- Application was configured for PostgreSQL by default
- No `.env` file existed in backend directory
- `config.py` defaulted to PostgreSQL connection string

**Solution:**
Created `.env` file with SQLite configuration:
```bash
# backend/.env
DATABASE_URL=sqlite:///code_visualizer.db
SECRET_KEY=dev-secret-key-change-in-production
JWT_SECRET_KEY=dev-jwt-secret-key-change-in-production
FLASK_DEBUG=True
STORAGE_PATH=../storage
```

Also created frontend `.env`:
```bash
# frontend/.env
REACT_APP_API_URL=http://localhost:5000/api
```

### 2. Flask Reloader Error on Windows
**Error Message:** `[Errno 22] Invalid argument`

**Root Cause:**
- Flask's auto-reloader (`werkzeug`) has known compatibility issues on Windows
- Error occurred during request processing before route handlers executed
- Related to file handle management and temporary file operations on Windows

**Symptoms:**
- All API endpoints returned `[Errno 22] Invalid argument`
- Error appeared even on non-authenticated test endpoints
- No debug output from `before_request` hooks or route functions
- Error handler was called but error occurred before route execution

**Solution:**
Disabled Flask's auto-reloader in `app.py`:

```python
if __name__ == '__main__':
    from init_db import init_database
    init_database()
    # Disable reloader to avoid Windows-specific issues with file handles
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)
```

**Note:** Debug mode remains enabled for error messages and debugging. Only the auto-reloader is disabled.

### 3. Frontend Port Conflict
**Error Message:** `Something is already running on port 3000`

**Root Cause:**
- Previous React development server still running
- PID 33100 occupying port 3000

**Solution:**
```bash
taskkill //F //PID 33100
```

### 4. Lost User Accounts
**Issue:** User account created "yesterday" was not present in database

**Root Cause:**
- Fresh database was initialized during troubleshooting
- Previous database (if any) was replaced

**Solution:**
- Created utility script `create_admin.py` to recreate user accounts
- Database is persistent going forward with SQLite file storage

---

## Files Modified

### 1. `/backend/.env` (Created)
- Added SQLite database URL
- Configured JWT secrets
- Set storage path

### 2. `/backend/app.py`
**Changes:**
- Disabled Flask reloader: `use_reloader=False`
- Simplified error handler to avoid recursive errors
- Commented out debug logging that caused issues on Windows

**Before:**
```python
app.run(debug=True, host='0.0.0.0', port=5000)
```

**After:**
```python
app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)
```

### 3. `/backend/routes/projects.py`
**Changes:**
- Commented out `@projects_bp.before_request` logging hook
- Added detailed error handling in `create_project` function

### 4. `/frontend/.env` (Created)
- Set React app API URL to localhost:5000

---

## Database Initialization

Successfully initialized SQLite database:
```bash
cd backend
python init_db.py
```

**Database Location:** `backend/code_visualizer.db`

**Tables Created:**
- `users` - User authentication
- `projects` - Project management
- `analysis_results` - Code analysis data
- `workspace_notes` - User notes
- `workspace_layouts` - Workspace configurations

---

## Utility Scripts Created

### 1. `/backend/create_admin.py`
Creates admin user account programmatically.

**Usage:**
```bash
cd backend
python create_admin.py
```

**Default Credentials:**
- Username: `Admin`
- Password: `LocalHost`
- Email: `admin@localhost.com`

### 2. `/backend/check_users.py`
Lists all users in the database.

**Usage:**
```bash
cd backend
python check_users.py
```

### 3. `/backend/debug_db.py`
Tests database operations and model creation.

---

## Running the Application

### Backend
```bash
cd backend
python app.py
```
- Runs on http://localhost:5000
- Debug mode: ON
- Auto-reloader: OFF (Windows compatibility)

### Frontend
```bash
cd frontend
npm install  # First time only
npm start
```
- Runs on http://localhost:3000
- Connects to backend API automatically

---

## Testing Verification

All endpoints tested and confirmed working:

### Authentication
```bash
# Register
curl -X POST http://localhost:5000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"test","email":"test@example.com","password":"test123"}'

# Login
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"Admin","password":"LocalHost"}'
```

### Projects
```bash
# Create project (requires JWT token)
curl -X POST http://localhost:5000/api/projects \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"name":"My Project","description":"Test project"}'

# List projects
curl http://localhost:5000/api/projects \
  -H "Authorization: Bearer <token>"
```

---

## Known Limitations

### 1. No Hot Reload
- Code changes require manual server restart
- This is a Windows-specific limitation to avoid file handle errors

### 2. Manual User Creation
- Users created before fresh database initialization are lost
- Use `create_admin.py` script to recreate accounts

---

## Troubleshooting Guide

### Issue: "DATABASE_URL is not SQLite format"
**Check:**
1. `.env` file exists in `backend/` directory
2. `.env` contains: `DATABASE_URL=sqlite:///code_visualizer.db`

**Fix:**
```bash
cd backend
cp .env.example .env
# Edit DATABASE_URL to use SQLite
```

### Issue: "[Errno 22] Invalid argument"
**Check:**
1. `app.py` has `use_reloader=False`
2. No Python processes are stuck running

**Fix:**
```bash
taskkill //F //IM python.exe
cd backend
python app.py
```

### Issue: "Port 3000 already in use"
**Check:**
```bash
netstat -ano | findstr :3000
```

**Fix:**
```bash
taskkill //F //PID <process_id>
```

### Issue: "Invalid token" / "Signature verification failed"
**Cause:** Token expired (1 hour expiration)

**Fix:** Login again to get fresh token

### Issue: Can't create projects
**Check:**
1. Backend is running (http://localhost:5000)
2. Valid JWT token in Authorization header
3. Database initialized properly

**Fix:**
```bash
cd backend
python init_db.py
python app.py
```

---

## Future Recommendations

### For Production
1. **Use PostgreSQL** instead of SQLite for better concurrency
2. **Enable reloader** on Linux/Mac environments
3. **Set strong secrets** in production `.env` file
4. **Use production WSGI server** (gunicorn, waitress)

### For Development
1. **Keep reloader disabled** on Windows
2. **Backup database** before major changes:
   ```bash
   cp backend/code_visualizer.db backend/code_visualizer.db.backup
   ```
3. **Clear Python cache** if seeing stale code:
   ```bash
   find . -type d -name __pycache__ -exec rm -rf {} +
   find . -name "*.pyc" -delete
   ```

---

## Success Metrics

- ✓ Backend starts without errors
- ✓ Frontend starts without errors
- ✓ Database initializes correctly
- ✓ User registration works
- ✓ User login works
- ✓ Project creation works
- ✓ JWT authentication works
- ✓ CORS configured properly
- ✓ All API endpoints functional

---

## Additional Notes

### Cache Clearing
If changes to Python files don't take effect:
```bash
cd backend
find . -type d -name __pycache__ -exec rm -rf {} +
find . -name "*.pyc" -delete
```

### Database Reset
To start with fresh database:
```bash
cd backend
rm code_visualizer.db
python init_db.py
python create_admin.py  # Recreate admin user
```

### Frontend Dependency Issues
If frontend won't start:
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
npm start
```

---

## Contact & References

**Documentation:** `/docs/`
**Issue Tracking:** GitHub Issues
**Related Files:**
- `backend/app.py` - Main Flask application
- `backend/config.py` - Configuration management
- `backend/database.py` - SQLite connection handler
- `backend/init_db.py` - Database initialization
- `README.md` - General setup instructions
