# MCP Server Setup Guide

This document explains the Model Context Protocol (MCP) servers configured for the Etymology Explorer project.

## What is MCP?

MCP (Model Context Protocol) extends Claude Code with specialized tools for databases, browsers, APIs, and more. Instead of using bash workarounds like `docker exec`, Claude can directly query MongoDB, control browsers, and interact with services.

## Configured MCP Servers

### 1. MongoDB MCP (`mongodb-mcp-server`)

**Purpose**: Direct MongoDB database access

**Configuration**:
```json
{
  "type": "stdio",
  "command": "npx",
  "args": ["-y", "mongodb-mcp-server"],
  "env": {
    "MONGODB_URI": "mongodb://localhost:27017",
    "MONGODB_DATABASE": "etymology"
  }
}
```

**Prerequisites**:
- Docker containers running (`make run`)
- MongoDB container healthy

**Example Usage**:
```
> List all collections
> Show me 5 sample documents from the words collection
> Query for English words derived from Latin
> Count total documents in the database
> What's the structure of documents in the words collection?
```

**Tools Provided**:
- List databases and collections
- Query documents with filters
- Run aggregation pipelines
- Create/update/delete documents
- Manage indexes
- Database statistics

---

### 2. Playwright MCP (`@executeautomation/playwright-mcp-server`)

**Purpose**: Browser automation and frontend testing

**Configuration**:
```json
{
  "type": "stdio",
  "command": "npx",
  "args": ["-y", "@executeautomation/playwright-mcp-server"]
}
```

**Prerequisites**:
- Frontend running at http://localhost:8080

**Example Usage**:
```
> Open localhost:8080 and take a screenshot
> Test the search functionality - search for "wine"
> Click on a node in the graph and verify the detail panel appears
> Check if the graph renders with all nodes visible
> Test the language filter dropdown
> Verify zoom controls work
```

**Tools Provided**:
- Navigate to URLs
- Click elements / fill forms
- Take screenshots
- Execute JavaScript in browser context
- Wait for elements/conditions
- Extract page content

---

### 3. GitHub MCP (HTTP)

**Purpose**: Enhanced GitHub integration

**Configuration**:
```json
{
  "type": "http",
  "url": "https://api.githubcopilot.com/mcp/"
}
```

**Prerequisites**:
- Authentication via `/mcp` command (browser OAuth)

**Example Usage**:
```
> Review the latest PR and suggest improvements
> What issues are currently open?
> Show me the commit history for graph.js
> Create a new issue for the uncertain etymology feature
```

**Tools Provided**:
- PR creation/review/management
- Issue tracking
- Repository insights
- Commit history analysis
- Code search across repo

---

## Setup Instructions

### Initial Setup (Already Done)

The MCP servers are configured in `.mcp.json` at project root. This file is committed to the repo, so MCP tools are available for all developers.

### Using MCP Tools

1. **Start a new Claude Code session** in this project directory
2. MCP tools are **automatically loaded** at session startup
3. Simply ask Claude to use them naturally:
   - ❌ Don't: `docker exec ... mongosh ...`
   - ✅ Do: "List collections in the database"

### Verifying Setup

```bash
# Check all configured MCP servers and connection status
claude mcp list

# Check MongoDB specifically
claude mcp get mongodb

# Check Playwright
claude mcp get playwright
```

Expected output:
```
mongodb: npx -y mongodb-mcp-server - ✓ Connected
playwright: npx -y @executeautomation/playwright-mcp-server - ✓ Connected
github: https://api.githubcopilot.com/mcp/ (HTTP) - ⚠ Needs authentication
```

### Authenticating GitHub MCP

1. In Claude Code, type: `/mcp`
2. Follow the browser OAuth flow
3. Return to Claude Code
4. GitHub MCP tools are now available

---

## Troubleshooting

### MongoDB Shows "Failed to connect"

**Cause**: Docker containers not running or MongoDB unhealthy

**Solution**:
```bash
make run                    # Start containers
docker ps                   # Verify "healthy" status
claude mcp list            # Verify connection
```

### Playwright Shows "Failed to connect"

**Cause**: Playwright installation issue

**Solution**:
```bash
npx -y @executeautomation/playwright-mcp-server --help
# Should download and show help
```

### MCP Tools Not Available in Claude

**Cause**: Session started before .mcp.json was present, or tools haven't loaded

**Solution**:
- Exit and restart Claude Code session
- MCP tools load at startup, not mid-session

### Tools Not Working Despite Connection

**Cause**: Tool Search mode may be filtering tools

**Check**:
```bash
# See current tool search settings
echo $ENABLE_TOOL_SEARCH

# Disable if needed (loads all tools upfront)
ENABLE_TOOL_SEARCH=false claude
```

---

## Adding New MCP Servers

To add additional MCP servers to this project:

```bash
# Add at project scope (shared via .mcp.json)
claude mcp add --scope project --transport stdio server-name -- npx -y package-name

# With environment variables
claude mcp add --scope project --transport stdio \
  --env KEY1=value1 \
  server-name -- npx -y package-name

# For HTTP servers
claude mcp add --scope project --transport http server-name https://url
```

After adding, edit `.mcp.json` if needed and commit the changes.

---

## Benefits of MCP Approach

**Before MCP (bash workarounds)**:
```bash
docker exec etymograph-mongodb-1 mongosh etymology --eval "db.words.find({lang: 'en'}).limit(5)"
```
- Hard to parse output
- Limited to terminal capabilities
- Requires Docker and MongoDB knowledge
- Error-prone command construction

**With MCP (natural language)**:
```
> Show me 5 English words from the database
```
- Natural language queries
- Structured responses
- Context-aware results
- Handles edge cases automatically

---

## Package Information

| Server | Package | Version | Docs |
|--------|---------|---------|------|
| MongoDB | `mongodb-mcp-server` | 1.5.0 | [npm](https://www.npmjs.com/package/mongodb-mcp-server) |
| Playwright | `@executeautomation/playwright-mcp-server` | Latest | [npm](https://www.npmjs.com/package/@executeautomation/playwright-mcp-server) |
| GitHub | HTTP endpoint | - | [Claude Code docs](https://code.claude.com/docs/en/mcp.md) |

---

## Next Steps

1. **Start a new Claude Code session** to load the MCP tools
2. **Try MongoDB queries**: "List collections", "Show sample documents"
3. **Test the frontend**: "Test search on localhost:8080"
4. **Authenticate GitHub** (if needed): Use `/mcp` command

For more information, see the [official Claude Code MCP documentation](https://code.claude.com/docs/en/mcp.md).
