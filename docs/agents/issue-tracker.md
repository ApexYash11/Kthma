# Issue tracker: Local Markdown

Issues and specs for this repo live as markdown files in `.scratch/`.

This is a solo hackathon repo with no usable GitHub remote. Local files are the tracker.

## Conventions

- One feature per directory: `.scratch/<feature>/`
- The spec is `.scratch/<feature>/spec.md`
- Implementation issues are one file per ticket at `.scratch/<feature>/issues/<nn>-<slug>.md`, numbered from `01`, never a single combined tickets file
- Status is a `Status:` line near the top of each issue file
- Comments append under a `## Comments` heading

## When a skill says "publish to the issue tracker"

Create a new file under `.scratch/<feature>/` (creating the directory if needed).

## When a skill says "fetch the relevant ticket"

Read the file at the referenced path. The user will normally pass the path or the issue number directly.
