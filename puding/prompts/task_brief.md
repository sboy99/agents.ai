You are implementing one task from an auto-generated plan for a product idea.
The task was written by a planning pipeline, not by a human who has read this
repository, so treat the brief as a good-faith specification: follow it
closely, and where it is ambiguous or wrong, make the nearest sensible choice
and report what you decided.

# {id} — {title}

**Area:** {area}

## Why this task exists

{prd}

## Acceptance criteria

The ticket is done when every item below is verifiably true. These are the
definition of done, not a suggestion list.

{criteria}

## Relevant excerpt from the spec

This is the low-level design for the area above. It may be truncated and may
end mid-block; if a detail you need is missing, say so rather than inventing
the rest of the design.

{spec_excerpt}

## Stack

{stack}

## Out of scope

Do not change, refactor, or "improve" anything listed here. If your change
cannot avoid touching it, stop and flag the conflict instead of proceeding.

{out_of_scope}

## How to work this task

1. Read the acceptance criteria and the spec excerpt before writing any code.
2. Inspect the repository and follow its existing patterns — module layout,
   naming, error handling, and testing style win over your preferences.
3. Check what already exists for this area. The plan may be stale; if part of
   the work is done, build on it rather than duplicating it.
4. Implement the smallest change that satisfies every acceptance criterion.
5. Add tests for the new behaviour using the repository's existing test setup,
   then run them along with the existing suite.
6. Fix failures you caused. Report, but do not fix, unrelated preexisting
   failures.

## What to return when finished

- A summary of what you changed, with file paths.
- Each acceptance criterion marked verified or not, naming the command or test
  that proves it.
- Any place you guessed, deviated from the spec, or hit a conflict with the
  out-of-scope list.
- Anything you deliberately left undone.
