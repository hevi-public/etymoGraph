# Agent-to-Agent Code Review Guidelines

## Purpose

Code review between agents ensures that code merged into the project is **readable**, **maintainable**, and **understandable** — not just functional. The human owner should be able to open any file months later and follow what it does without the agents present.

---

## Roles

**Author Agent** — wrote the code, opens it for review.
**Reviewer Agent** — reads the code cold, provides feedback.

The author knows *intent*. The reviewer represents *a fresh reader*. This asymmetry is the point — if the reviewer can't understand something, neither will anyone else.

---

## Review Process

### 1. Author Prepares the Review

Before requesting review, the author provides:

```
## Review Request

### What changed
[1-3 sentence summary of the change and why it was made]

### Files changed
[List of files, in reading order — most important first]

### How to verify
[How to test that it works — API calls, UI actions, etc.]

### Concerns
[Anything the author is unsure about or wants specific feedback on]
```

The author does NOT pre-explain the code. The reviewer should be able to understand it from reading alone. If they can't, that's the first finding.

### 2. Reviewer Reads Cold

The reviewer reads every changed file without asking the author questions first. They form their own understanding of:

- What does this code do?
- Why does it exist?
- How does it connect to the rest of the codebase?

If any of these are unclear from the code alone, that is a review finding — the code needs clarification, not the review.

### 3. Reviewer Produces Findings

Findings are categorized by severity:

| Level | Meaning | Action Required |
|-------|---------|-----------------|
| **MUST** | Bugs, security issues, broken behavior | Fix before merge |
| **SHOULD** | Readability problems, unclear intent, missing context | Fix unless author justifies |
| **CONSIDER** | Style preferences, minor improvements, alternative approaches | Author's discretion |

Each finding follows this format:

```
### [MUST/SHOULD/CONSIDER] Short title

**File**: path/to/file.js:42-58
**Issue**: What's wrong or unclear
**Suggestion**: Concrete fix (not just "make it better")
```

### 4. Author Responds

For each finding, the author either:

- **Fixes** it (preferred)
- **Explains** why the current code is correct/intentional (reviewer may accept or push back)
- **Defers** with a tracked TODO (only for CONSIDER items)

### 5. Reviewer Confirms

Reviewer re-reads changed files and confirms all MUST/SHOULD items are resolved. Review is complete.

---

## What to Look For

### Readability (Can I follow this?)

- **Naming**: Do variable/function names describe what they hold/do? Would a reader unfamiliar with the codebase guess correctly?
- **Flow**: Can you read top-to-bottom without jumping around? Are there surprising control flow paths?
- **Length**: Are functions short enough to hold in your head? (Guideline: if you need to scroll, it's probably too long.)
- **Comments**: Are non-obvious decisions explained? Are there comments that just restate the code? (Remove those.)
- **Formatting**: Is indentation and spacing consistent with the rest of the codebase?

### Maintainability (Can I change this safely?)

- **Coupling**: If I change this code, how many other files break? Fewer is better.
- **Hardcoded values**: Are there magic numbers or strings that should be constants or config?
- **Error handling**: Does the code fail gracefully? Are error messages useful for debugging?
- **State**: Is mutable state minimized? Can you trace where a value comes from?
- **Duplication**: Is there copy-pasted logic that should be shared? (But don't over-abstract — three similar lines are fine.)

### Understandability (Do I know WHY this exists?)

- **Intent**: Is it clear what problem this code solves? Not just *what* it does, but *why*?
- **Architecture**: Does this fit the existing patterns in the codebase, or does it introduce a new pattern? If new, is there a good reason?
- **Data flow**: Can you trace inputs to outputs? Are transformations obvious?
- **Edge cases**: Are boundary conditions handled? Are they commented if non-obvious?
- **Names over comments**: Could a better name eliminate the need for a comment?

---

## Review Checklist

The reviewer works through this for every changed file:

```
[ ] I can describe what this file/function does without reading comments
[ ] All names are accurate and descriptive
[ ] No dead code, commented-out code, or TODOs without context
[ ] Error paths are handled and produce useful messages
[ ] No security issues (injection, XSS, exposed secrets, etc.)
[ ] Consistent with existing codebase patterns
[ ] No unnecessary complexity (YAGNI)
[ ] Changes are documented where required (FEATURES.md, CLAUDE.md, etc.)
```

---

## Anti-Patterns to Reject

These are common in agent-generated code and should be flagged:

1. **Stale comments** — Comment says one thing, code does another. Common after edits.
2. **Over-engineering** — Abstraction layers, config options, or error handling for scenarios that don't exist.
3. **Implicit dependencies** — Code that only works because of load order, global state, or undocumented assumptions.
4. **Naming lies** — `formatText()` that also modifies DOM. `getUser()` that creates one if missing.
5. **Silent failures** — `catch (e) {}` or swallowed errors with no logging.
6. **Cargo-culted patterns** — Code copied from elsewhere without understanding why it was written that way.
7. **Inconsistent style** — New code that doesn't match the conventions of the file it's in.
8. **God functions** — Single functions doing 5+ distinct things. Split them.

---

## Principles

1. **The code is the documentation.** If it needs a paragraph of explanation, rewrite it.
2. **Optimize for the reader, not the writer.** Code is read 10x more than it's written.
3. **Every line should earn its place.** If removing a line changes nothing, remove it.
4. **Be specific.** "This is confusing" is not a finding. "Rename `d` to `descendantNodes` on line 42" is.
5. **Review the change, not the person.** Findings are about code, not judgment.
