---
name: aws_docs_mcp
description: Use before writing or editing Terraform, AWS SDK code (boto3 / @aws-sdk), IAM policies, or AWS CLI commands — or before stating any AWS identifier, API shape, region code, or service limit — to verify it against the official AWS docs MCP rather than recalling it. NOT for casual mentions of AWS in unrelated chat.
---

# AWS Documentation MCP — verify AWS facts, don't recall them

If the official AWS documentation MCP server is connected, it exposes:

- `mcp__aws-docs__search_documentation` — search AWS docs by keyword
- `mcp__aws-docs__read_documentation` — fetch a specific docs URL
- `mcp__aws-docs__read_sections` — read named sections of a docs page
- `mcp__aws-docs__recommend` — related docs / "what's new" for a service

**Prefer this MCP over web search, web fetch, or training knowledge** for any
AWS work. AWS APIs change often and training data lags behind; guessing an
argument name produces a broken Terraform plan or a failing SDK call. Reach for
it whenever you are:

- Writing or editing **Terraform** (`*.tf`, `terragrunt.hcl`) — verify resource
  argument names, valid values, deprecations, and provider version diffs.
- Writing code against an **AWS SDK** — `boto3` (Python), `@aws-sdk/client-*`
  v3 or `aws-sdk` v2 (Node) — confirm method signatures, parameter shapes,
  error classes, and paginators.
- Writing **IAM** policies or trust relationships — verify action names,
  condition keys, and ARN patterns.
- Composing **AWS CLI** commands — confirm flag names and output shapes before
  piping into `jq`.
- Investigating service-specific errors — Lambda timeouts, DynamoDB throttling,
  S3 access-denied, Secrets Manager rotation, EventBridge routing, and the like.

**Workflow:** start with `search_documentation` for the service + topic, then
`read_documentation` (or `read_sections`) on the most relevant URL. Use
`recommend` for adjacent or "what's new" pages. Cite the docs URL when you
state a fact back to the user.

**If the tools are not present in this session**, the MCP is not installed or
registered. Install the official AWS documentation MCP server through your host
agent's MCP registry (add its server entry to the agent's MCP config), then
restart the session. The registration is idempotent — safe to re-run if the
entry ever drifts.

This skill is about *verification discipline*, not a particular cloud: when you
are about to assert an AWS identifier — a region code, a model id, an ARN
pattern, an API shape — and you have not confirmed it this session, confirm it
here first. "I'd need to check" beats a confident wrong identifier.
