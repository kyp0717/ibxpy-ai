# TWS Trading App Context Engineering 
This file provides guidance for working with code in this repository.  
It contains rules for python development and deployment 

## Virtual Environment - CRITICAL - ALWAYS USE UV
- **ALWAYS use `uv` for ALL Python operations - DO NOT manually activate venv**
- **NEVER use `source .venv/bin/activate` - use `uv run` instead**
- **NEVER install packages globally**
- **Use `uv run` for ALL Python commands:**
  ```bash
  uv run python script.py        # NOT: python script.py
  uv run pytest                  # NOT: pytest
  uv run uvicorn main:app        # NOT: uvicorn main:app
  ```
- **Use `uv pip` for package management:**
  ```bash
  uv pip install <package>       # NOT: pip install
  uv pip install -r requirements.txt
  ```
- **The virtual environment was created with `uv` (version 0.8.11)**

## Version Control
- At the end of each stage, git add, commit and push the changes.
- Create a new branch once the stage has ended and git push has completed.
- At the start of a new stage, create a new git branch and switch to new branch
  before development.
- Name the new branch with this format `hybrid-stage-xx` .

## IBAPI Library Reference
- **IBAPI is installed in**: `.venv/lib/python3.13/site-packages/ibapi/`
- **Source location** (if needed): `~/Downloads/twsapi/IBJts/source/pythonclient/`
- **Import check**: `python -c "import ibapi; print(ibapi.__version__)"`
- **TWS Connection**: localhost:7497 (paper), localhost:7496 (live)
- See `context/ibapi-config.md` for detailed configuration

## Project Structure
```
ibxpy-ai/
├── .venv/              # Virtual environment (Python 3.13)
├── src/                # Application source code
├── backend/            # FastAPI backend (new)
├── tests/              # Unit and integration tests
├── docs/               # Documentation
├── scripts/            # Helper and installation scripts
└── context/            # AI context and planning
    ├── project-plan/   # Development phases
    ├── logs/           # Phase completion logs
    ├── tasks.md        # Current tasks
    └── requirements.md # Project requirements
```

## Project Awareness & Context
- At the start of a new conversation, read files in `context/project-plan/` to review project's architecture, style, and constraints
- Read `context/tasks.md` to understand current work status
- Read `context/requirements.md` for technical requirements
- Review session log files in `context/logs/` to understand project progress

## Development Workflow

### 1. Always Use UV Commands
```bash
# Verify uv is available
uv --version  # Should show 0.8.11 or higher

# Check Python version in venv
uv run python --version  # Should show Python 3.13.6
```

### 2. Installing Dependencies
```bash
# Backend dependencies
cd backend && uv pip install -r requirements.txt

# Project dependencies  
uv pip install -r pyproject.toml

# Install IBAPI
uv pip install ~/Downloads/twsapi/IBJts/source/pythonclient/
```

### 3. Running Code
```bash
# Run backend
cd backend && uv run uvicorn main:app --reload

# Run tests
uv run pytest

# Run main app
uv run python src/main.py AAPL 100

# Run any Python script
uv run python path/to/script.py
```

## Testing 
- **IMPORTANT: Always use the python-phase-tester agent (Task tool with subagent_type: "general-purpose") for implementing all phase tests**
- **ALWAYS use `uv run` for testing:**
  ```bash
  uv run pytest                    # Run all tests
  uv run pytest tests/test_file.py # Run specific test
  uv run python -m pytest -v       # Verbose testing
  ```
- Tests are located in `/tests` at the project root
- Create unit tests for new features
- Run tests to verify changes don't break existing functionality
- **After updating any logic**, check whether existing unit tests need to be updated

## Logs (Claude Context)
- **IMPORTANT** - After the successful completion of each phase, log the
summary!
- Logs folder is in `context/logs/` - these are Claude-specific phase summaries
- When each phase is completed successfully, create a concise, high level summary
- Log summary should be no more than 16 lines
- Each summary should have 1 heading only and several bullet points
- Do not use icons in the log files
- The format should be: `stagexx-phasexx-yyyymmdd.md`
- If a phase is reimplemented, append to existing log with timestamp

## Scripts 
- All shell scripts are located in `/scripts` at the project root
- Installation scripts should use `uv`:
  ```bash
  uv pip install ...  # For package installation
  uv run python ...   # For running Python scripts
  ```

## Documents 
- All documentation is in `/docs` at the project root:
  - `/docs/architecture/` - System design docs
  - `/docs/api/` - API specifications
  - `/docs/installation/` - Setup guides

## General Principles
- **Never assume missing context. Ask questions if uncertain**
- **Never hallucinate libraries or functions** – only use known, verified Python packages
- **Always confirm file paths and module names** exist before referencing them
- **Never delete or overwrite existing code** unless explicitly instructed
- **ALWAYS use virtual environment** for any Python operations

## Implementation Guidelines

### Adding New Features
1. **Use `uv run` for all Python commands**
2. **Module Structure**
   - Create new file in appropriate directory (`src/`, `backend/`)
   - Follow existing patterns
   
3. **Testing**
   - Create unit tests in `tests/`
   - Run tests: `uv run pytest`
   
4. **Development Process**
   - Follow TDD: RED → GREEN → REFACTOR
   - Each feature must be independent and self-contained
   - Ask for permission before adding new methods to existing modules

## Structure & Modularity
- **Never create a file longer than 500 lines** - refactor if approaching limit
- **Organize code into clearly separated modules** by feature/responsibility
- **Never hardcode sensitive information** - use .env files

## Backend Development (FastAPI)
When working on backend:
```bash
# Navigate to backend
cd backend

# Install dependencies
uv pip install -r requirements.txt

# Run development server
uv run uvicorn main:app --reload

# Run tests
uv run pytest

# Run with specific port
uv run uvicorn main:app --reload --port 8001
```

## Important Reminders
1. **ALWAYS USE UV**: Use `uv run` for ALL Python commands - NEVER manually activate venv
2. **Package Management**: Use `uv pip` not `pip`
3. **IBAPI**: Already installed in `.venv/lib/python3.13/site-packages/ibapi/`
4. **Testing**: Run all tests with `uv run pytest`
5. **Dependencies**: Check requirements.txt and pyproject.toml
6. **Running Scripts**: `uv run python script.py` NOT `python script.py`
- Please update the context to remember that at each stage of the development, create a new branch with the name 'hybrid-stage-xx`.
