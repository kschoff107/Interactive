@echo off
echo ========================================
echo Code Visualizer - Quick Start (SQLite)
echo ========================================
echo.

REM Copy SQLite versions
echo Setting up SQLite compatibility...
copy /Y database_sqlite.py database.py
copy /Y init_db_sqlite.py init_db.py
echo.

REM Install dependencies (minimal for quick start)
echo Installing dependencies...
pip install Flask Flask-JWT-Extended Flask-CORS werkzeug python-dotenv --quiet
echo.

REM Initialize database
echo Creating SQLite database...
python init_db.py
echo.

REM Start the server
echo Starting Flask server...
echo.
echo Backend API available at: http://localhost:5000
echo Press Ctrl+C to stop
echo.
python app.py
