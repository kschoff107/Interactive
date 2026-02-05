# Code Visualizer

A web application that helps visual learners understand backend systems by analyzing code and generating interactive visualizations.

## Features

- 🔐 User authentication with JWT
- 📁 Project management
- 🐍 SQLAlchemy model parser
- 📊 Database schema visualization
- 🎨 Clean, modern UI with Tailwind CSS

## Prerequisites

- Python 3.10+
- Node.js 18+
- PostgreSQL 14+

## Quick Start

### 1. Set Up PostgreSQL

Create the database:
```bash
createdb code_visualizer_dev
```

Or using psql:
```sql
psql -U postgres
CREATE DATABASE code_visualizer_dev;
\q
```

### 2. Set Up Backend

```bash
cd backend

# Windows
setup_and_run.bat

# Mac/Linux
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env and set DATABASE_URL
python init_db.py
python app.py
```

**Important:** Edit `backend/.env` and set your DATABASE_URL:
```
DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/code_visualizer_dev
```

The backend API will be available at **http://localhost:5000**

### 3. Set Up Frontend (in a new terminal)

```bash
cd frontend

# Windows
setup_and_run.bat

# Mac/Linux
npm install
cp .env.example .env
npm start
```

The frontend will be available at **http://localhost:3000**

## Usage

1. **Register a new account** at http://localhost:3000/register
2. **Login** with your credentials
3. **Create a project** in the dashboard
4. **Upload Python files** with SQLAlchemy models
5. **View the analyzed database schema**

## Project Structure

```
code-visualizer/
├── backend/                 # Flask backend
│   ├── models/             # Database models
│   ├── routes/             # API endpoints
│   ├── parsers/            # Code parsers
│   ├── tests/              # Test suite
│   ├── app.py              # Main application
│   └── init_db.py          # Database initialization
├── frontend/               # React frontend
│   ├── src/
│   │   ├── components/    # UI components
│   │   ├── context/       # React context
│   │   └── services/      # API services
│   └── public/
└── storage/               # Uploaded files storage

```

## API Endpoints

### Authentication
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login user

### Projects
- `GET /api/projects` - List user's projects
- `POST /api/projects` - Create new project
- `GET /api/projects/:id` - Get project details
- `POST /api/projects/:id/upload` - Upload files for analysis

## Tech Stack

**Backend:**
- Flask 3.x
- PostgreSQL with psycopg2
- JWT authentication
- Python AST for code parsing

**Frontend:**
- React 18
- React Router
- Axios
- Tailwind CSS
- React Toastify

## Development

### Running Tests

```bash
cd backend
pytest
```

### Database Reset

If you need to reset the database:
```bash
cd backend
python
>>> from init_db import init_database
>>> init_database()
```

## Contributing

This is a personal project. Feel free to fork and modify!

## License

MIT
