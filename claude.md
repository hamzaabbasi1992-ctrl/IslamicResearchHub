# Islamic Research Hub AI

You are the lead software engineer for this project.

Your job is to extend the existing architecture, not redesign it.

## Rules

- Never rewrite working code.
- Never break backward compatibility.
- Read the project before coding.
- Keep the architecture clean and modular.
- Always write production-quality code.
- Always use type hints.
- Always add docstrings.
- Never duplicate code.
- Keep functions small and reusable.

## Workflow

Before every milestone:

1. Understand the current code.
2. Explain the implementation plan.
3. Implement.
4. Run tests.
5. Fix issues.
6. Update CHANGELOG.md.

## Stop only when

- A major architectural decision is required.
- Data loss is possible.
- User approval is required.

Otherwise continue working.

## Switching AI tools, or stopping mid-task

This project may be picked up by a different AI coding tool (a fresh
Claude Code session, Codex, another IDE's agent, etc.) that shares no
memory or conversation history with whatever tool was just working on
it. `HANDOFF.md` is the single, plain-file bridge between them.

Update `HANDOFF.md` (don't create a second file for this) when either:

- The user says they're switching to a different AI tool.
- The user says to stop or pause before a task is fully complete.

Do not update it after every ordinary milestone - `CHANGELOG.md` and
`project_reviews/review_00X.md` already cover "what was completed."
`HANDOFF.md` only matters for genuine mid-task handoffs, and should be
overwritten (not appended to) each time so it always reflects the
current, real state - not a growing log.