# Agent-to-Agent Code Review Guidelines

## Purpose

Code review between agents ensures that code merged into the project is **readable**, **maintainable**, and **understandable** — not just functional. The human owner should be able to open any file months later and follow what it does without the agents present.

---

## Roles

**Developer Agent (DA)** — wrote the code, opens a PR for review.
**Review Agent (RA)** — reads the code cold, reviews the PR.

The author knows *intent*. The reviewer represents *a fresh reader*. This asymmetry is the point — if the reviewer can't understand something, neither will anyone else.

---

## Review Process

All reviews happen through GitHub Pull Requests using the `gh` CLI.

### 1. DA Opens a Pull Request

The DA creates a branch, commits changes, and opens a PR with a structured description (the repo has a PR template that guides this):

```bash
gh pr create --title "Short description" --body "$(cat <<'EOF'
## What changed
[1-3 sentence summary of the change and why it was made]

## Files changed
[List of files, in reading order — most important first]

## How to verify
[How to test that it works — API calls, UI actions, etc.]

## Concerns
[Anything the author is unsure about or wants specific feedback on]
EOF
)"
```

The DA does NOT pre-explain the code. The reviewer should be able to understand it from reading alone. If they can't, that's the first finding.

DA notifies the human:
> "PR #N opened: [title]. URL: [link]. **Next**: Assign the Review Agent to review this PR."

### 2. RA Reviews the Pull Request

The RA reads the PR diff cold using `gh`:

```bash
gh pr view <N>
gh pr diff <N>
```

They form their own understanding of:
- What does this code do?
- Why does it exist?
- How does it connect to the rest of the codebase?

If any of these are unclear from the code alone, that is a review finding.

The RA leaves findings as:
- **Inline comments** on specific lines for file/line-specific issues
- **A summary review** with overall assessment and finding counts

Findings are categorized by severity:

| Level | Meaning | Action Required |
|-------|---------|-----------------|
| **MUST** | Bugs, security issues, broken behavior | Fix before merge |
| **SHOULD** | Readability problems, unclear intent, missing context | Fix unless author justifies |
| **CONSIDER** | Style preferences, minor improvements, alternative approaches | Author's discretion |

Inline comment format:
```
**[MUST/SHOULD/CONSIDER]**: Short title

**Issue**: What's wrong or unclear
**Suggestion**: Concrete fix (not just "make it better")
```

The RA submits their review:
```bash
gh pr review <N> --comment --body "$(cat <<'EOF'
## Review Summary

| Level | Count |
|-------|-------|
| MUST | X |
| SHOULD | Y |
| CONSIDER | Z |

**Overall**: [1-2 sentence summary of code quality]

See inline comments for details.
EOF
)"
```

RA notifies the human:
> "PR #N reviewed. X MUST, Y SHOULD, Z CONSIDER findings. URL: [link]. **Next**: Assign the Developer Agent to address findings."

### 3. DA Responds to Findings

The DA reads review comments and replies to each one:

```bash
# Read review comments
gh api repos/{owner}/{repo}/pulls/{N}/comments
```

For each finding, the DA replies on the comment thread with one of:

| Response | Meaning | When to use |
|----------|---------|-------------|
| **Accept** | DA agrees and will fix | Finding is clearly correct |
| **Counter** | DA proposes an alternative fix | DA sees a better solution than suggested |
| **Challenge** | DA believes current code is correct | DA has context the reviewer lacked |

For **Counter** and **Challenge** responses, the DA MUST provide:
- **Evidence**: Code references, data format examples, or behavioral proof — not opinions
- **Proposed resolution**: A concrete alternative (for Counter) or explanation of why the status quo is correct (for Challenge)

The DA pushes fixes for accepted items and requests re-review.

DA notifies the human:
> "Responded to all findings on PR #N. Accepted X, countered Y, challenged Z. Pushed fixes. URL: [link]. **Next**: Assign the Review Agent to re-evaluate."

### 4. RA Re-reviews

The RA re-reads the diff, evaluates responses to countered/challenged findings:

- **Accept responses**: Verified fix was pushed.
- **Counter responses**: Evaluates the alternative. Accepts if it has merit, or explains why the original suggestion is stronger. If both sides have merit, defaults to **DA's preference** — the author owns the code.
- **Challenge responses**: Evaluates the evidence. If it holds, the finding is withdrawn. If not, restates with additional context.

If satisfied:
```bash
gh pr review <N> --approve --body "All findings resolved. LGTM."
```

If not:
```bash
gh pr review <N> --request-changes --body "Remaining issues: ..."
```

RA notifies the human:
> "PR #N approved/changes requested. [Summary]. URL: [link]. **Next**: Merge the PR if satisfied / Assign DA to address remaining issues."

### 5. Tiebreaking Rules

If DA and RA still disagree after one round:

1. **MUST findings**: Reviewer wins. Safety and correctness are non-negotiable.
2. **SHOULD findings**: Whoever provides stronger evidence wins. If evidence is equal, **author decides** — they carry the maintenance burden.
3. **CONSIDER findings**: Author always wins. These are preferences by definition.

No finding may go more than **two rounds** of back-and-forth. If unresolved after two rounds, apply the tiebreaker above and move on.

---

## Human Action Summary

Every step of the review process must end with a clear notification to the human. Agents cannot merge, deploy, or make final judgment calls — only the human owner can.

| Step | Agent notifies human with |
|------|--------------------------|
| **1. DA opens PR** | PR URL, title, summary. "Assign the Review Agent to review." |
| **2. RA reviews** | Finding counts, PR URL. "Assign the Developer Agent to address findings." |
| **3. DA responds** | Accept/counter/challenge counts, PR URL. "Assign the Review Agent to re-evaluate." |
| **4. RA re-reviews** | Approval or remaining issues, PR URL. "Merge if satisfied / assign DA for remaining issues." |

This ensures the human is never left wondering "what now?" after an agent hands off.

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
