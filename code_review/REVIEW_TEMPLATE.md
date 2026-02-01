# Review Agent Comment Format Reference

This document describes how the Review Agent (RA) should structure their GitHub PR review comments. The actual review happens on the PR itself — this is a formatting reference only.

---

## Inline Comments (on specific lines)

For each finding, leave an inline comment on the relevant line(s):

```
**[MUST/SHOULD/CONSIDER]**: Short title

**Issue**: What's wrong or unclear
**Suggestion**: Concrete fix (not just "make it better")
```

Example:
```
**[SHOULD]**: Rename ambiguous variable

**Issue**: `d` on line 42 could mean anything — data, document, descendant
**Suggestion**: Rename to `descendantNodes` to match its contents
```

---

## Summary Review

After leaving inline comments, submit a summary review using `gh pr review`:

```
## Review Summary

| Level | Count |
|-------|-------|
| MUST | X |
| SHOULD | Y |
| CONSIDER | Z |

**Overall**: [1-2 sentence assessment of code quality]

See inline comments for details.
```

---

## Responding to Author Replies

When the DA responds to findings, the RA evaluates each reply:

- **Accept**: Verify the fix was pushed. No further comment needed.
- **Counter**: Evaluate the alternative. Reply with agreement or explain why the original is stronger.
- **Challenge**: Evaluate the evidence. Reply with withdrawal or restatement with additional context.

---

## Final Review Submission

- If all findings are resolved: `gh pr review <N> --approve --body "All findings resolved. LGTM."`
- If issues remain: `gh pr review <N> --request-changes --body "Remaining issues: ..."`

---

## Severity Reference

| Level | Meaning | Action Required |
|-------|---------|-----------------|
| **MUST** | Bugs, security issues, broken behavior | Fix before merge |
| **SHOULD** | Readability problems, unclear intent, missing context | Fix unless author justifies |
| **CONSIDER** | Style preferences, minor improvements, alternative approaches | Author's discretion |
