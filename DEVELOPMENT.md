# Development Guide

Quick start guide for developers (human or AI) working on Etymology Explorer.

## First-Time Setup

```bash
# 1. Install development tools
make setup-dev

# This installs:
# - Python dev dependencies (pytest, ruff, pre-commit)
# - Node.js dev dependencies (eslint)
# - Pre-commit hooks (runs automatically on git commit)
```

## Daily Development Workflow

### Before Writing Code

1. **Read the coding standards**: `docs/CODING_STANDARDS.md`
2. **Check current status**: See `CLAUDE.md` "Current Status" section
3. **Review relevant docs**:
   - `docs/FEATURES.md` - Feature documentation
   - `code_review/GUIDELINES.md` - PR review process

### While Writing Code

**Follow the standards**:
- **Python**: Type hints + Google-style docstrings for all functions
- **JavaScript**: Small pure functions (<80 lines), meaningful names
- **Both**: Contextual comments explaining *why*, not *what*

**Common patterns**:

```python
# Python - Good
def process_word(word: str, lang: str) -> dict:
    """Process a word entry.

    Args:
        word: The word to process
        lang: Language of the word

    Returns:
        Processed word data as dict
    """
    return {"word": word, "lang": lang}

# JavaScript - Good
function buildNodeId(word, lang) {
    return `${word}:${lang}`;
}

/**
 * Extract ancestry from etymology templates.
 * Only includes templates matching allowed types.
 *
 * @param {Object} doc - Kaikki document
 * @param {Set<string>} allowedTypes - Connection types to include
 * @returns {Array} Ancestry chain
 */
function extractAncestry(doc, allowedTypes) {
    // ... implementation
}
```

### Before Committing

```bash
# 1. Run linters (optional - pre-commit hooks will do this)
make lint

# 2. Format code (optional - pre-commit hooks will do this)
make format

# 3. Run tests
make test

# 4. Update FEATURES.md if you changed behavior
vim docs/FEATURES.md

# 5. Commit (hooks run automatically)
git add .
git commit -m "[TASK_ID]: Brief description"
```

### Pre-commit Hooks

**Runs automatically on `git commit`**:
- Ruff (Python): linting + formatting
- ESLint (JavaScript): linting

**If violations found**:
- Commit is blocked
- Error messages show what to fix
- Fix issues and retry commit

**Auto-fix**:
- Most formatting issues are fixed automatically
- Re-stage files after auto-fix: `git add .`
- Retry commit

### Pull Request Process

See `code_review/GUIDELINES.md` for full details.

**Summary**:
1. **Developer Agent (DA)** opens PR with structured description
2. **Review Agent (RA)** reviews for standards compliance + correctness
3. **DA** responds to findings (accept/counter/challenge)
4. **RA** re-reviews and approves or requests changes
5. **Human** merges when satisfied

## Common Tasks

### Run Specific Tests

```bash
# All tests
cd backend && pytest

# Specific file
cd backend && pytest tests/test_etymology_classifier.py

# Specific test
cd backend && pytest tests/test_etymology_classifier.py::test_detect_uncertainty_from_templates_unk

# Verbose output
cd backend && pytest -v
```

### Fix Linting Issues

```bash
# Check what's wrong
make lint

# Auto-fix Python
cd backend && ruff check --fix .

# Auto-format Python
make format

# Auto-fix JavaScript
npx eslint frontend/public/js/**/*.js --fix
```

### Add a New Test

1. Create test file in `backend/tests/test_<module>.py`
2. Follow naming convention: `test_<function>_<scenario>`
3. Use Arrange-Act-Assert structure
4. Mark async tests with `@pytest.mark.asyncio`
5. Run: `cd backend && pytest tests/test_<module>.py`

**Example**:
```python
"""Tests for new_module."""
import pytest
from app.services.new_module import new_function

def test_new_function_basic():
    """Test new_function with valid input."""
    # Arrange
    input_data = "test"

    # Act
    result = new_function(input_data)

    # Assert
    assert result == "expected"
```

### Add a New Service

1. Create file: `backend/app/services/new_service.py`
2. Add docstring at top: `"""Brief description of service."""`
3. Write functions with type hints and docstrings
4. Create tests: `backend/tests/test_new_service.py`
5. Run tests: `cd backend && pytest tests/test_new_service.py`

### Check Coding Standards

**Quick reference**:
```bash
# Full standards
cat docs/CODING_STANDARDS.md

# Python section only
grep -A 50 "## Python Standards" docs/CODING_STANDARDS.md

# JavaScript section only
grep -A 50 "## JavaScript Standards" docs/CODING_STANDARDS.md

# Examples section
grep -A 100 "## Examples" docs/CODING_STANDARDS.md
```

### Troubleshooting

**Pre-commit hooks not running**:
```bash
pre-commit install  # Re-install hooks
```

**Linter not found**:
```bash
make setup-dev  # Re-install dependencies
```

**Tests fail with import errors**:
```bash
cd backend
export PYTHONPATH=$PWD:$PYTHONPATH
pytest
```

**Can't commit due to hook errors**:
```bash
# See what's wrong
make lint

# Fix manually or auto-fix
make format
npx eslint frontend/public/js/**/*.js --fix

# Bypass hooks (NOT recommended - use only in emergencies)
git commit --no-verify -m "Emergency commit"
```

## Development Commands Reference

```bash
# Setup
make setup         # Full project setup (Docker, data, MongoDB)
make setup-dev     # Development tools only (linters, hooks)

# Running
make run           # Start all services (Docker Compose)
make stop          # Stop all services
make logs          # View logs

# Code Quality
make lint          # Run all linters (Ruff + ESLint)
make format        # Format Python code
make test          # Run all tests

# Data
make download      # Download Kaikki data
make load          # Load data into MongoDB
make update        # Force re-download + reload data

# Cleanup
make clean         # Remove data and containers
```

## Key Files Reference

### Documentation
- `docs/CODING_STANDARDS.md` - **START HERE** - All coding standards
- `docs/FEATURES.md` - Feature documentation (update before committing)
- `code_review/GUIDELINES.md` - PR review process
- `CLAUDE.md` - Project overview and conventions
- `README.md` - User-facing setup guide

### Configuration
- `pyproject.toml` - Ruff configuration (Python linting)
- `.eslintrc.json` - ESLint configuration (JavaScript linting)
- `.pre-commit-config.yaml` - Pre-commit hooks configuration
- `docker-compose.yml` - Docker services configuration
- `.env` - Environment variables (copy from `.env.example`)

### Code Structure
- `backend/app/main.py` - FastAPI app entry point
- `backend/app/routers/` - API endpoints (thin layer)
- `backend/app/services/` - Business logic (where the work happens)
- `backend/tests/` - Test files
- `frontend/public/js/` - JavaScript code
- `frontend/public/index.html` - Main HTML page

## Best Practices

### Do
- ✅ Read CODING_STANDARDS.md before coding
- ✅ Run `make test` before pushing
- ✅ Update FEATURES.md when changing behavior
- ✅ Write small, focused functions
- ✅ Add type hints and docstrings
- ✅ Use meaningful variable names
- ✅ Add contextual comments for non-obvious code

### Don't
- ❌ Skip running tests
- ❌ Commit without updating FEATURES.md (if behavior changed)
- ❌ Bypass pre-commit hooks (unless emergency)
- ❌ Over-engineer (keep it simple)
- ❌ Write functions over 80 lines
- ❌ Add backwards-compatibility hacks
- ❌ Commit code with linting errors

## Getting Help

### Documentation
- **Coding standards**: `docs/CODING_STANDARDS.md`
- **Feature status**: `docs/FEATURES.md`
- **Review process**: `code_review/GUIDELINES.md`
- **Test guide**: `backend/tests/README.md`

### Verification
- **Setup verification**: `CODING_STANDARDS_SETUP.md`
- **Implementation summary**: `IMPLEMENTATION_SUMMARY.md`

### Tools
- **Ruff docs**: https://docs.astral.sh/ruff/
- **Pytest docs**: https://docs.pytest.org/
- **ESLint docs**: https://eslint.org/docs/
- **FastAPI docs**: https://fastapi.tiangolo.com/

## Quick Checklist

Before opening a PR:

```
[ ] Code follows CODING_STANDARDS.md
[ ] All functions have type hints (Python)
[ ] All functions have docstrings (Python)
[ ] Functions are small (<80 lines)
[ ] Tests written for business logic
[ ] All tests pass (make test)
[ ] Linters pass (make lint)
[ ] FEATURES.md updated (if behavior changed)
[ ] PR description follows template
```

---

**Happy coding!** 🚀
