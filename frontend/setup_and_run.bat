@echo off
echo ========================================
echo Code Visualizer - Frontend Setup
echo ========================================
echo.

REM Create .env file if it doesn't exist
if not exist ".env" (
    echo Creating .env file...
    copy .env.example .env
    echo.
)

REM Install dependencies
echo Installing dependencies...
call npm install
echo.

REM Start the development server
echo Starting React development server...
echo The app will open at http://localhost:3000
echo Press Ctrl+C to stop the server
echo.
call npm start
