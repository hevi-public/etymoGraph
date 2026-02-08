# Coding Standards

## Purpose

This document defines coding standards for the Etymology Explorer project to ensure code is **readable**, **maintainable**, and **understandable** by both humans and LLM agents. These standards balance quality with pragmatism — avoid over-engineering while maintaining clarity.

**Philosophy**: Clean Code + Functional Paradigm. Heavy use of small pure functions that are expressive in themselves. Consider code readability from both human and LLM perspective.

---

## Table of Contents

1. [Python Standards](#python-standards)
2. [JavaScript Standards](#javascript-standards)
3. [General Principles](#general-principles)
4. [Documentation Standards](#documentation-standards)
5. [Git Workflow](#git-workflow)
6. [Testing Standards](#testing-standards)
7. [Enforcement & Tooling](#enforcement--tooling)
8. [Examples](#examples)

---

## Python Standards

### Type Hints

**Required**: All functions must have type hints for parameters and return values.

- Use Python 3.10+ syntax: `str | None` instead of `Optional[str]`
- Use `dict[str, Any]` instead of `Dict[str, Any]`
- Import from `collections.abc` for container types if needed

```python
# Good
async def find_descendants(word: str, lang: str, lc: str,
                          parent_level: int, depth: int = 0) -> None:
    pass

# Bad - missing type hints
async def find_descendants(word, lang, lc, parent_level, depth=0):
    pass
```

### Docstrings

**Required**: All functions must have Google-style docstrings.

**Format**:
```python
def function_name(param1: str, param2: int) -> dict:
    """Brief one-line summary.

    Optional longer description explaining the purpose, algorithm, or non-obvious
    behavior. Explain the *why*, not just the *what*.

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        Description of return value

    Raises:
        HTTPException: When X condition occurs
    """
```

**What to document**:
- **Args**: Purpose and constraints of each parameter
- **Returns**: What is returned and its structure
- **Raises**: Exceptions that callers should handle
- **Why not what**: Explain the reasoning behind non-obvious logic

**Simple functions**: One-line docstring is acceptable if the function is self-explanatory.

```python
def node_id(word: str, lang: str) -> str:
    """Return unique node ID for a word in a language."""
    return f"{word}:{lang}"
```

### Error Handling

**Database operations**: Wrap in try/except, use `HTTPException` with clear messages.

```python
from fastapi import HTTPException

try:
    doc = await col.find_one({"word": word, "lang": lang})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Word '{word}' not found in {lang}")
except Exception as e:
    raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
```

**Don't over-engineer**: Only validate at system boundaries (user input, external APIs). Trust internal code and framework guarantees.

### Async/Await

- **Always await** database calls in async functions
- No blocking operations in async functions
- Use `async def` for FastAPI route handlers and any functions that call async code

### File Organization

- **Routers**: Thin layer, validation, call services
- **Services**: Business logic, database queries, transformations
- **No logic in routers**: Extract to services layer

```python
# Good - router.py
@router.get("/etymology/{word}/tree")
async def get_etymology_tree(word: str, lang: str = "English"):
    """Build a full etymology tree."""
    col = get_words_collection()
    builder = TreeBuilder(col, allowed_types, max_ancestor_depth, max_descendant_depth)
    await builder.expand_word(word, lang, base_level=0)
    return builder.result()

# Bad - logic in router
@router.get("/etymology/{word}/tree")
async def get_etymology_tree(word: str, lang: str = "English"):
    col = get_words_collection()
    doc = await col.find_one({"word": word, "lang": lang})
    # ... 50 lines of tree building logic ...
```

### Code Style

- **Line length**: 100 characters (Ruff configured)
- **Naming**: `snake_case` for functions/variables, `PascalCase` for classes
- **Imports**: Group by stdlib, third-party, local (Ruff handles this)
- **String quotes**: Double quotes `"` (Ruff configured)

---

## JavaScript Standards

### Function Extraction

**Extract logic into small pure functions** (<50 lines ideal, <80 acceptable).

**When to extract**:
- Logic can be tested independently
- Function has multiple responsibilities
- Code is hard to understand at a glance
- Repeated patterns appear

```javascript
// Good - extracted utility functions
function escapeHtml(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function buildTemplateLookup(templates) {
    const lookup = {};
    // ... focused logic ...
    return lookup;
}

// Bad - monolithic function with multiple responsibilities
function processData(data) {
    // 100 lines mixing escaping, lookup building, and rendering
}
```

### Naming

- **Functions**: Verb phrases describing action (`buildTemplateLookup`, `renderGraph`)
- **Variables**: Noun phrases describing contents (`etymologyText`, `nodeId`)
- **Constants**: UPPER_SNAKE_CASE (`MAX_DESCENDANTS`)
- **Meaningful names**: Avoid abbreviations unless obvious (`doc` is fine, `d` is not)

### JSDoc

**Use JSDoc for complex functions** with non-obvious parameters or behavior.

```javascript
/**
 * Build lookup from templates for linkable terms.
 *
 * @param {Array} templates - Etymology templates from Kaikki entry
 * @returns {Object} Lookup map: word → {word, lang_code}
 */
function buildTemplateLookup(templates) {
    // ...
}
```

**Simple functions**: No JSDoc needed if self-explanatory.

### Error Handling

**API calls**: Wrap in try/catch, show user-facing error messages.

```javascript
// Good
async function loadGraph(word, lang) {
    try {
        const data = await getEtymologyTree(word, lang, types);
        renderGraph(data);
    } catch (error) {
        showError(`Failed to load etymology for "${word}": ${error.message}`);
    }
}

// Bad - no error handling
async function loadGraph(word, lang) {
    const data = await getEtymologyTree(word, lang, types);
    renderGraph(data);
}
```

**Don't over-engineer**: Don't add error handling for scenarios that can't happen.

### State Management

- **Avoid global state**: Migrate to module pattern or state object
- **Current approach**: Global variables in `graph.js` (`network`, `searchedWordId`, etc.) — acceptable for now, but refactor when touching that code

### Code Style

- **Semicolons**: Always use `;` at end of statements
- **Quotes**: Double quotes `"`
- **Indentation**: 4 spaces
- **Line length**: ~120 characters (ESLint warning)
- **File size**: Split files over 500 lines into focused modules

---

## General Principles

### Function Extraction

**Proactively extract logic into small functions** when implementing or modifying code.

**Benefits**:
- Improves readability and testability
- Makes codebase easier to understand for humans and LLMs
- Reduces cognitive load

**Example from `graph.js`**:
```javascript
// Good - clear, testable functions
function escapeHtml(s) { /* ... */ }
function buildTemplateLookup(templates) { /* ... */ }
function splitEtymologySections(text) { /* ... */ }

// Bad - 100-line function mixing all concerns
function formatEtymologyText(text, templates) {
    // escaping, lookup building, section splitting all mixed together
}
```

### Contextual Comments

**Add brief comments explaining *why***, not *what*.

```python
# Good - explains reasoning
# Only include if this ancestor is the IMMEDIATE parent
first_ancestry = extract_ancestry(doc, self.allowed_types)

# Bad - restates code
# Get first ancestry
first_ancestry = extract_ancestry(doc, self.allowed_types)

# Good - explains trade-off
# Kaikki stores the full ancestry chain on each word, but we only
# use the first template to determine the immediate parent
```

**When to add contextual comments**:
- Non-obvious decisions or trade-offs
- Workarounds for data quirks
- Context that future readers need

### Avoid Over-Engineering

**Only make changes directly requested or clearly necessary.**

- Don't add features beyond what was asked
- Don't refactor code you're not changing
- Don't add docstrings/comments to code you didn't touch
- Don't add error handling for impossible scenarios
- Don't create abstractions for one-time operations
- Don't design for hypothetical future requirements

**Three similar lines are better than a premature abstraction.**

### Backwards Compatibility

**Don't add backwards-compatibility hacks** like:
- Renaming unused variables to `_vars`
- Re-exporting types
- Adding `// removed` comments for deleted code

**If something is unused, delete it completely.**

---

## Documentation Standards

### FEATURES.md Updates

**REQUIRED**: Update `docs/FEATURES.md` before committing any feature or behavior change.

**What to document**:
- New features and how to use them
- Changed behavior and migration notes
- API endpoint changes
- Known limitations

This is an existing rule, reinforced by these standards.

### Contextual Comments

**Add comments explaining *why***, not *what*.

```python
# Good
# TreeBuilder uses only the first ancestry template to determine the direct parent,
# even though Kaikki stores the full chain on each word. This prevents duplicates
# in the graph.
first_ancestry = extract_ancestry(doc)

# Bad
# Extract ancestry
first_ancestry = extract_ancestry(doc)
```

### API Documentation

FastAPI auto-generates docs at `/docs`. Ensure:
- Route docstrings are clear and accurate
- Parameter descriptions use `Query(description=...)`
- Response models are documented

---

## Git Workflow

### Commit Format

```
[TASK_ID]: Brief description of change

Optional longer description explaining the reasoning behind the change.
```

**Example**: `P2.3: Add cognate expansion with recursion limit`

### Commit Guidelines

- **Document first, commit second**: Always update `docs/FEATURES.md` before committing feature changes
- Commit after each completed task
- Each commit should be a logical unit of work

### Pull Request Process

See `code_review/GUIDELINES.md` for the full DA/RA review process.

**Key points**:
- DA opens PR with structured description (what, files, how to verify, concerns)
- RA reviews for coding standards compliance (MUST level violations)
- DA responds to findings (accept/counter/challenge)
- RA re-reviews and approves or requests changes

---

## Testing Standards

### What to Test

**Required**:
- All services layer functions (`tree_builder.py`, `template_parser.py`, `etymology_classifier.py`, etc.)
- All utility functions with complex logic

**Optional**:
- Simple routers (FastAPI handles most validation)
- Basic UI interactions (use Playwright MCP for manual testing)

### Testing Framework

- **Python**: pytest + pytest-asyncio
- **JavaScript/UI**: Playwright MCP (manual testing)

### Test Structure

```python
"""Tests for TreeBuilder service."""
import pytest
from app.services.tree_builder import TreeBuilder

@pytest.mark.asyncio
async def test_expand_word_basic():
    """Test basic word expansion with simple ancestry."""
    # Arrange
    col = await test_db()
    builder = TreeBuilder(col, {"inh"}, 10, 3)

    # Act
    await builder.expand_word("cheese", "English", base_level=0)
    result = builder.result()

    # Assert
    assert len(result["nodes"]) > 0
    assert result["nodes"][0]["label"] == "cheese"
```

### Test Coverage

- **Business logic**: 100% coverage expected
- **Routers**: Basic happy path coverage
- **UI**: Manual testing with Playwright MCP

---

## Enforcement & Tooling

### Pre-commit Hooks

**Strict blocking**: Violations block commits (must fix before committing).

**Configured tools**:
- **Ruff** (Python): Linting + formatting
- **ESLint** (JavaScript): Linting

**Setup**:
```bash
make setup-dev  # Installs pre-commit hooks + dependencies
```

**Manual runs**:
```bash
make lint    # Run linters
make format  # Format code
make test    # Run tests
```

### Code Review

**Review Agent enforces standards during PR review** (MUST level for violations).

**Checklist**:
- Type hints and docstrings present (Python)
- Functions are appropriately sized
- Error handling present for system boundaries
- No over-engineering or unnecessary abstractions
- FEATURES.md updated (if applicable)

### Migration Strategy

**Gradual adoption**:
- All new code follows standards immediately (enforced by pre-commit hooks)
- Existing code refactored opportunistically when touched
- No requirement to refactor entire files at once

**No mass refactoring required** — quality improves incrementally.

---

## Examples

### Example 1: Router with Missing Docstrings (BEFORE)

**File**: `backend/app/routers/etymology.py`

```python
@router.get("/etymology/{word}/chain")
async def get_etymology_chain(word: str, lang: str = "English", max_depth: int = 10):
    """Trace ancestry chain upward from a word to its root."""
    col = get_words_collection()
    # ... implementation ...
```

**Issues**:
- Missing type hints for return value
- Docstring doesn't document parameters or return value

**AFTER** (following standards):

```python
@router.get("/etymology/{word}/chain")
async def get_etymology_chain(
    word: str,
    lang: str = "English",
    max_depth: int = 10
) -> dict:
    """Trace ancestry chain upward from a word to its root.

    Builds a linear chain from the given word through its etymological ancestors
    up to the specified depth or until no further ancestry is found.

    Args:
        word: The word to trace ancestry for
        lang: Language of the word (default: English)
        max_depth: Maximum number of ancestor levels to trace

    Returns:
        dict with keys:
            - nodes: List of node objects (id, label, language, level)
            - edges: List of edge objects (from, to, label)
    """
    col = get_words_collection()
    # ... implementation ...
```

### Example 2: Large Function Needing Extraction (BEFORE)

**File**: `frontend/public/js/graph.js` (~930 lines)

**Issues**:
- Very large file mixing multiple concerns
- Some functions are long and hard to test

**AFTER** (guidance, not full refactor):

When adding features to `graph.js`:
- Extract new logic into focused functions
- Consider splitting into modules: `graph-core.js`, `graph-formatting.js`, `graph-events.js`
- Apply when file grows beyond 1000 lines or when adding significant new features

### Example 3: Good Service Layer Documentation (EXISTING)

**File**: `backend/app/services/etymology_classifier.py`

```python
def detect_uncertainty_from_templates(templates: list[dict]) -> UncertaintyResult | None:
    """Check etymology_templates for unk/unc markers.

    Returns UncertaintyResult if found, None otherwise.
    """
    for tmpl in templates:
        name = tmpl.get("name", "")
        if name in UNCERTAINTY_TEMPLATES:
            uncertainty_type = "unknown" if name == "unk" else "uncertain"
            return UncertaintyResult(
                is_uncertain=True,
                uncertainty_type=uncertainty_type,
                source=f"template:{name}",
                confidence="high",
            )
    return None
```

**Good practices**:
- Clear type hints
- Concise docstring explaining purpose and return value
- Simple, focused function
- Meaningful variable names

### Example 4: Error Handling in API Client (EXISTING)

**File**: `frontend/public/js/api.js`

```javascript
async function searchWords(query) {
    const res = await fetch(`${API_BASE}/search?q=${encodeURIComponent(query)}&limit=20`);
    if (!res.ok) throw new Error("Search failed");
    return res.json();
}
```

**Good practices**:
- Checks response status
- Throws error with clear message
- Caller can catch and handle appropriately

**Could improve** (when touching this file):
```javascript
async function searchWords(query) {
    try {
        const res = await fetch(`${API_BASE}/search?q=${encodeURIComponent(query)}&limit=20`);
        if (!res.ok) {
            throw new Error(`Search failed: ${res.status} ${res.statusText}`);
        }
        return await res.json();
    } catch (error) {
        throw new Error(`Failed to search for "${query}": ${error.message}`);
    }
}
```

---

## Summary

**Core principles**:
1. **Type hints and docstrings** for all Python functions
2. **Small, focused functions** in both Python and JavaScript
3. **Contextual comments** explaining *why*, not *what*
4. **Error handling** at system boundaries only
5. **Update FEATURES.md** before committing feature changes
6. **No over-engineering** — keep it simple
7. **Gradual migration** — apply standards to new code and code you touch

**Enforcement**:
- Pre-commit hooks block violations
- Review Agent enforces during PR review
- No mass refactoring required

**Remember**: Code is read 10x more than it's written. Optimize for the reader.
