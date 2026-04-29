# Burrow — Requirements

Version: 0.0.1
Date: 2026-04-29
Author: SN

---

## Introduction

Burrow is a terminal tool for reviewing code changes produced by coding agents (e.g. Codex, Claude Code). A human reviewer inspects a diff in the terminal, attaches structured comments to specific locations in the diff, and triggers the coding agent to address those comments. Burrow exchanges JSON with the agent: a Request carrying the reviewer's comments goes out, and a Response comes back from the agent.

Burrow is not an agent. It is the interface between a human reviewer and an agent. It does not generate code, interpret comments, or decide how to act on them — that is the agent's responsibility.

---

## Glossary

| Term | Definition |
|---|---|
| Agent | An external coding agent (e.g. Codex, Claude Code) that receives comments and produces code changes. Burrow treats the agent as a black box. |
| Comment | A structured annotation attached to a location in a diff by the reviewer, expressing a concern, request, or observation. |
| Diff | A set of file changes, expressed as a unified diff, that the reviewer is evaluating. |
| Request | A JSON payload sent to the agent containing the reviewer's comments for a session. |
| Response | A JSON payload returned by the agent in reply to a Request. |
| Reviewer | The human operator using Burrow in the terminal to inspect a diff and author comments. |
| Session | A single review lifecycle: from loading a diff to dispatching a Request to the agent and receiving a Response. |

---

## Overview

_To be completed once the first capabilities and scenarios are agreed._

```mermaid
flowchart TD
    placeholder([TBD])
```

---

## Capabilities

_To be populated as capabilities are agreed._

---

## Tag Glossary

### Standard tags

| Tag | Meaning |
|---|---|
| `interface` | Exchange of data between components: interchange formats, APIs and protocols. |
| `security` | Authentication, authorisation, data protection, auditing. |
| `data` | Correctness, completeness, validation and storage of data. |
| `error` | Failure modes, warnings, operator messages, recovery. |
| `operational` | Deployment, installation, maintenance, monitoring. |
| `performance` | Throughput, latency, resource usage. |
| `networking` | Network access, protocols, connectivity. |
| `regulatory` | Compliance, risk controls, audit requirements. |
| `configuration` | Behaviour governed by configurable parameters. |
| `usability` | User interface, user experience, accessibility. |

### Project-specific tags

_None defined yet._

---

## Deferred Decisions

| # | Question |
|---|---|
| D-1 | How does Burrow invoke the agent — subprocess, HTTP, stdin/stdout pipe? The JSON exchange protocol implies a boundary but the transport is not yet decided. |
| D-2 | Does Burrow persist sessions across invocations, or is each run stateless? |
| D-3 | Is the diff always sourced from git, or can it be provided as a file? |
