# Coding Standards Implementation - Verification Checklist

This document provides verification steps for the coding standards implementation.

## Files Created

### Documentation
- ✅ `docs/CODING_STANDARDS.md` - Comprehensive coding standards (17KB)
- ✅ `backend/tests/README.md` - Test structure and conventions

### Configuration Files
- ✅ `pyproject.toml` - Ruff configuration (Python linting + formatting)
- ✅ `.eslintrc.json` - ESLint configuration (JavaScript linting)
- ✅ `.pre-commit-config.yaml` - Pre-commit hooks configuration
- ✅ `package.json` - ESLint dependency + scripts
- ✅ `backend/requirements-dev.txt` - Development dependencies

### Test Files
- ✅ `backend/tests/__init__.py`
- ✅ `backend/tests/conftest.py` - Pytest fixtures
- ✅ `backend/tests/test_tree_builder.py` - TreeBuilder tests (basic + TODOs)
- ✅ `backend/tests/test_etymology_classifier.py` - Full test coverage for classifier

### Modified Files
- ✅ `CLAUDE.md` - Updated Conventions section to reference CODING_STANDARDS.md
- ✅ `code_review/GUIDELINES.md` - Added coding standards compliance to review criteria
- ✅ `Makefile` - Added setup-dev, lint, test, format targets
- ✅ `docs/FEATURES.md` - Added Development & Code Quality section
- ✅ `.gitignore` - Added test artifacts (.pytest_cache, .coverage, etc.)

## Verification Steps

### 1. Setup Development Tools

```bash
make setup-dev
```

**Expected output**:
- Installing Python development dependencies...
- Installing Node.js development dependencies...
- Installing pre-commit hooks...
- Development setup complete!

**Verify**:
```bash
# Check pre-commit is installed
pre-commit --version

# Check Ruff is installed
ruff --version

# Check ESLint is installed
npx eslint --version
```

### 2. Run Linters on Existing Code

```bash
make lint
```

**Expected behavior**:
- Ruff runs on `backend/` directory
- ESLint runs on `frontend/public/js/**/*.js`
- Violations will be reported (existing code doesn't meet all standards yet)

**Example violations to expect**:
- Missing type hints in some router functions
- Missing docstrings in some functions
- Line length violations
- Unused imports

**Note**: These violations are expected and acceptable. The gradual migration strategy means existing code will be fixed opportunistically when touched.

### 3. Test Pre-commit Hook

**Create a test file with violations**:

```bash
# Create a Python file with violations
cat > /tmp/test_violations.py << 'EOF'
def bad_function(x, y):
    # Missing type hints and docstring
    return x+y
EOF

# Move to backend directory
mv /tmp/test_violations.py backend/test_violations.py

# Try to commit
git add backend/test_violations.py
git commit -m "Test: intentional violations"
```

**Expected behavior**:
- Pre-commit hook runs automatically
- Ruff detects violations and blocks commit
- Error messages show what needs to be fixed

**Fix and retry**:
```bash
# Remove test file
rm backend/test_violations.py

# Or fix it
cat > backend/test_violations.py << 'EOF'
def good_function(x: int, y: int) -> int:
    """Add two integers.

    Args:
        x: First integer
        y: Second integer

    Returns:
        Sum of x and y
    """
    return x + y
EOF

# Now commit should succeed
git add backend/test_violations.py
git commit -m "Test: proper function with type hints"

# Clean up
rm backend/test_violations.py
```

### 4. Run Tests

```bash
make test
```

**Expected output**:
- pytest discovers and runs tests in `backend/tests/`
- `test_etymology_classifier.py`: All tests should pass (full coverage)
- `test_tree_builder.py`: Unit tests pass, async tests skip (need test DB)

**Example passing output**:
```
======================== test session starts =========================
backend/tests/test_etymology_classifier.py ................ [ 90%]
backend/tests/test_tree_builder.py ...                      [100%]

======================== 19 passed in 0.5s ==========================
```

### 5. Format Code

```bash
make format
```

**Expected behavior**:
- Ruff formats all Python files in `backend/`
- Files are reformatted to match style (double quotes, line length 100)
- No errors (formatting is non-destructive)

### 6. Manual Lint Check

Run linters individually to see detailed output:

**Python**:
```bash
cd backend
ruff check .
ruff check --output-format=json . | head -20  # JSON output for debugging
```

**JavaScript**:
```bash
npx eslint frontend/public/js/**/*.js
npx eslint frontend/public/js/graph.js --fix  # Auto-fix specific file
```

### 7. Verify Documentation

**Read key sections**:
```bash
# Main standards document
cat docs/CODING_STANDARDS.md | head -100

# Updated CLAUDE.md conventions
grep -A 20 "## Conventions" CLAUDE.md

# Updated review guidelines
grep -A 10 "## Review Criteria" code_review/GUIDELINES.md

# Features documentation
grep -A 20 "## Development & Code Quality" docs/FEATURES.md
```

**Checklist**:
- [ ] CODING_STANDARDS.md is comprehensive and actionable
- [ ] Examples are clear and from actual codebase
- [ ] All sections are present (Python, JS, Testing, Git, etc.)
- [ ] CLAUDE.md references CODING_STANDARDS.md
- [ ] GUIDELINES.md includes coding standards in review criteria
- [ ] FEATURES.md documents the implementation

### 8. Test Workflow Integration

**Simulate PR review workflow**:

1. Make a small change that violates standards:
   ```python
   # In backend/app/routers/etymology.py
   # Remove type hint from a function
   ```

2. Try to commit:
   ```bash
   git add backend/app/routers/etymology.py
   git commit -m "Test: violation"
   ```

3. Pre-commit hook should block with clear error message

4. Fix the violation and retry

5. Commit should succeed

### 9. Verify Makefile Targets

```bash
# Help text
make help  # (if implemented) or just run make

# Individual targets
make setup-dev  # Should complete without errors
make lint       # Should run both Ruff and ESLint
make test       # Should run pytest
make format     # Should format Python code
```

### 10. Check Configuration Validity

**Ruff config**:
```bash
cd backend
ruff check --show-settings
```

**ESLint config**:
```bash
npx eslint --print-config frontend/public/js/app.js
```

**Pre-commit config**:
```bash
pre-commit validate-config
pre-commit run --all-files  # Dry run on all files (will take time)
```

## Success Criteria

- ✅ All configuration files exist and are valid
- ✅ Pre-commit hooks block commits with violations
- ✅ Linters run without errors (violations in existing code are acceptable)
- ✅ Tests run and pass (excluding TODOs)
- ✅ Documentation is complete and references are correct
- ✅ Makefile targets work as expected
- ✅ Both humans and LLM agents can follow the standards

## Migration Strategy Verification

**Verify gradual adoption approach**:

1. **New code**: Create a new function in a new file
   - Must pass pre-commit hooks (type hints, docstrings, linting)
   - Standards are enforced immediately

2. **Modified code**: Edit an existing file
   - Apply standards to changed functions only
   - No requirement to refactor entire file

3. **Untouched code**: Existing code with violations
   - Remains as-is until touched
   - No mass refactoring required

**Example workflow**:
```bash
# Create new service with proper standards
cat > backend/app/services/new_service.py << 'EOF'
"""New service with proper standards."""

def process_data(input: str) -> dict:
    """Process input data.

    Args:
        input: Input string to process

    Returns:
        Processed data as dict
    """
    return {"result": input.upper()}
EOF

# Try to commit
git add backend/app/services/new_service.py
git commit -m "Add new service"

# Should succeed (meets all standards)
```

## Troubleshooting

**Pre-commit hook not running**:
- Run `pre-commit install` manually
- Check `.git/hooks/pre-commit` exists

**Ruff not found**:
- Install with `pip install ruff`
- Or run `make setup-dev`

**ESLint not found**:
- Install with `npm install`
- Or run `make setup-dev`

**Tests fail with import errors**:
- Ensure you're in the `backend` directory when running pytest
- Check that `backend` is in PYTHONPATH: `export PYTHONPATH=$PWD/backend:$PYTHONPATH`

**Pre-commit hooks too slow**:
- Pre-commit caches dependencies after first run
- Subsequent runs are much faster

## Next Steps

After verification:

1. **Update Current Status**: Update `CLAUDE.md` "Current Status" section to reflect standards implementation
2. **Create Test PR**: Make a small change following standards and test DA/RA workflow
3. **Document Lessons**: If any issues were found, update standards or troubleshooting docs
4. **Continue Development**: All new features should follow standards from now on

## Notes

- **No mass refactoring**: Existing code violations are acceptable and will be fixed opportunistically
- **Standards are enforced**: Pre-commit hooks block violations in new code
- **Review Agent aware**: RA will reference CODING_STANDARDS.md during reviews
- **Continuous improvement**: Standards can be updated based on experience

---

*Implementation completed: February 7, 2026*
