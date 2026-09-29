# FitBuddy – AI Fitness Plan Generator

**Academic Project**: Naan Mudhalvan  
**Domain**: Artificial Intelligence / Web Development  
**Current Phase**: Milestone 1 – Project Setup and Architecture

---

## 1. Project Overview

**FitBuddy** is an intelligent fitness and nutrition planning web application. It leverages modern Google Gemini Models to dynamically synthesize personalized workout routines, nutrition advice, and adaptive adjustments based on continuous user feedback.

### Technology Stack
- **Backend**: Python 3.13 / FastAPI (Asynchronous Web Framework)
- **Frontend**: HTML5, CSS3, Jinja2 Server-Side Template Rendering
- **Database**: SQLite with SQLAlchemy ORM
- **AI Integration**: Google Gen AI Python SDK (`google-genai`) with configurable model selection
- **Development Server**: Uvicorn ASGI Server

---

## 2. Project Architecture (Milestone 1)

```
FitBuddy/
├── app/
│   ├── __init__.py                # Package initialization
│   ├── main.py                    # FastAPI application initialization & static mounts
│   ├── routes.py                  # Web page and API route handlers
│   ├── database.py                # SQLAlchemy SQLite engine and session factory
│   ├── schemas.py                 # Pydantic data schemas and validation contracts
│   ├── gemini_generator.py        # Gemini AI workout generation client & logic
│   ├── gemini_flash_generator.py  # Fast nutrition/tips generator (Gemini Flash)
│   └── updated_plan.py            # Feedback-driven adaptive plan adjustment module
├── templates/
│   ├── index.html                 # Homepage with project overview and architecture status
│   ├── result.html                # Generated fitness plan preview template
│   └── all_users.html             # User database overview template
├── static/
│   ├── css/
│   │   └── style.css              # Responsive modern design theme
│   └── images/
│       └── .gitkeep               # Image assets placeholder
├── .env                           # Local environment configuration (API keys, models)
├── .env.example                   # Environment variable template
├── .gitignore                     # Git ignore rules for venv, env, and SQLite DB
├── requirements.txt               # Python package dependencies
└── README.md                      # Academic documentation and setup instructions
```

---

## 3. Windows Setup Instructions

Follow these steps to set up and run FitBuddy on Windows (using PowerShell or Command Prompt).

### Prerequisites
- Python 3.10+ installed and added to the Windows `PATH`.
- A Google AI Studio API key (optional for Milestone 1 placeholder verification, required for live AI responses).

---

### Step 1: Clone or Navigate to the Project Directory
Open **PowerShell** or **Command Prompt** and navigate to the project directory:
```powershell
cd d:\fitbuddy
```

---

### Step 2: Create a Python Virtual Environment
Create a dedicated virtual environment named `.venv`:
```powershell
python -m venv .venv
```

---

### Step 3: Activate the Virtual Environment

**In PowerShell:**
```powershell
.\.venv\Scripts\Activate.ps1
```
> *Note for PowerShell users:* If you receive an execution policy restriction error, run:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
> .\.venv\Scripts\Activate.ps1
> ```

**In Command Prompt (cmd.exe):**
```cmd
.\.venv\Scripts\activate.bat
```

When activated, you will see `(.venv)` in your command prompt.

---

### Step 4: Install Dependencies
Upgrade `pip` and install all required libraries from `requirements.txt`:
```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

---

### Step 5: Configure Environment Variables
Copy the `.env.example` file to `.env`:
```powershell
Copy-Item .env.example .env
```
Open `.env` in any text editor and configure your variables:
```env
# Paste your Gemini API key from Google AI Studio:
GOOGLE_API_KEY=your_actual_api_key_here

# Configurable Gemini Model (e.g., gemini-2.5-flash or gemini-2.5-pro):
GEMINI_MODEL=gemini-2.5-flash

# Server settings:
APP_ENV=development
PORT=8000
```
> **Security Notice**: Never commit `.env` to Git. The `.gitignore` file is pre-configured to keep your API key secure.

---

### Step 6: Run the Application
Start the Uvicorn ASGI development server with auto-reload:
```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

---

## 4. Verification & Testing Endpoints

Once the server is running, verify the application in your browser:

1. **Homepage**:  
   [http://127.0.0.1:8000/](http://127.0.0.1:8000/)  
   Displays the *FitBuddy – AI Fitness Plan Generator* landing page, displaying system status and architecture modules.

2. **Interactive API Documentation (Swagger UI)**:  
   [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)  
   Allows interactive testing of all API routes.

3. **System Health Check**:  
   [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)  
   Returns JSON status of backend, SQLite database connectivity, and configured Gemini model.

4. **Plan Preview Page**:  
   [http://127.0.0.1:8000/plans/preview](http://127.0.0.1:8000/plans/preview)

5. **Saved Users Page**:  
   [http://127.0.0.1:8000/users](http://127.0.0.1:8000/users)

---

## 5. File Breakdown and Architecture Roles

- **`app/main.py`**: Initializes the FastAPI application, mounts the `/static` directory for CSS/assets, and hooks up the lifespan event to initialize SQLite metadata.
- **`app/database.py`**: Establishes SQLite database engine using SQLAlchemy with `check_same_thread=False` for thread-safe asynchronous requests and provides the `get_db` dependency.
- **`app/routes.py`**: Handles incoming HTTP requests; renders Jinja2 HTML templates for UI views and provides health and generation endpoints.
- **`app/schemas.py`**: Pydantic models for request/response serialization and input validation.
- **`app/gemini_generator.py`**: Loads environment variables and provides client connection using the modern `google-genai` SDK with dynamically configurable models.
- **`app/gemini_flash_generator.py`**: Fast response generator module for quick nutrition tips and hydration guidelines.
- **`app/updated_plan.py`**: Dynamic update interface that adapts workout plans based on user feedback.
- **`templates/`**: Contains HTML templates (`index.html`, `result.html`, `all_users.html`) rendered via Jinja2.
- **`static/css/style.css`**: Responsive styling tailored for modern presentation.
