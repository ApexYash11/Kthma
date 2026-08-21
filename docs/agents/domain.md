# Domain Docs

How the engineering skills should consume this repo's domain documentation.

## Before exploring, read these

- `CONTEXT.md` at the repo root
- `docs/adr/` for ADRs that touch the area you're about to work in
- `AGENTS.md` for product constraints and phases

If an ADR directory is empty, proceed. `/grill-with-docs` and `domain-modeling` create ADRs when a real decision is resolved.

## File structure

Single-context repo:

```
/
├── AGENTS.md
├── CONTEXT.md
├── docs/adr/
└── docs/agents/
```

## Use the glossary's vocabulary

When output names a domain concept (issue title, test name, module name), use the term as defined in `CONTEXT.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept isn't in the glossary yet, either you're inventing language or there's a real gap. Note it for `domain-modeling`.

## Flag ADR conflicts

If output contradicts an existing ADR, surface it rather than silently overriding.
