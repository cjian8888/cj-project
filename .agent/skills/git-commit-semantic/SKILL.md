---
name: git-commit-semantic
description: Use when committing changes to git. Ensures commit messages follow semantic conventions and provide clear context for handovers.
---

# Semantic Git Commit Guide

## Overview
Standardizes Git commit messages to ensure project history is readable, automated tools can parse it, and handovers between different "agents" (sessions) are smooth.

## When to Use
- Before running any `git commit` command.
- When summarizing work for a handoff.
- Creating a PR title.

## Core Format
`<type>(<scope>): <subject>`

### Types
- **feat**: A new feature
- **fix**: A bug fix
- **docs**: Documentation only changes
- **style**: Changes that do not affect the meaning of the code (white-space, formatting, missing semi-colons, etc)
- **refactor**: A code change that neither fixes a bug nor adds a feature
- **perf**: A code change that improves performance
- **test**: Adding missing tests or correcting existing tests
- **chore**: Changes to the build process or auxiliary tools and libraries such as documentation generation

### Scope
The module or file affected (e.g., `backend`, `ui`, `report-engine`, `api`).

### Subject
Use the imperative, present tense: "change" not "changed" nor "changes". No dot at the end.

## Examples

```text
# Adding a new report section
feat(report-engine): add section 8 collision analysis

# Fixing a memory leak in analysis
fix(pandas): optimize dataframe memory usage in loop

# Updating docs
docs(readme): update installation instructions

# Refactoring UI
refactor(ui): extract Button component to separate file
```

## Handoff Context (The "Why")
For significant changes, add a body to the commit message explaining **why** this change was necessary. This is crucial for the "Multi-Agent Relay".

```text
fix(api): handle missing dob in profile extraction

The regex for extracting date of birth was failing on formats YYYY.MM instead of YYYY-MM.
Updated regex to support both. This unblocks the Phase 2 data cleaning.
```
