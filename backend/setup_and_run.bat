@echo off
echo ========================================
echo Code Visualizer - Backend Setup
echo ========================================
echo.

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    echo.
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate
echo.

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt
echo.

REM Create .env file if it doesn't exist
if not exist ".env" (
    echo Creating .env file...
    copy .env.example .env
    echo.
    echo IMPORTANT: Edit backend/.env and set your DATABASE_URL
    echo Example: DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/code_visualizer_dev
    echo.
    pause
)

REM Initialize database
echo Initializing database...
python init_db.py
echo.

REM Run the application
echo Starting Flask server...
echo The API will be available at http://localhost:5000
echo Press Ctrl+C to stop the server
echo.
python app.py
