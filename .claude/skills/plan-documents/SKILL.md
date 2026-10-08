---
name: plan-documents
description: Write a plan for work not yet started, for a colleague or the user to approve before implementation begins.
---

# Plan documents

The reader is deciding whether to let you proceed.

- Open questions and anything needing a decision go at the top.
- The steps, in order, one line each.
- Do not justify each step. Do not list the files you will touch. Do not
  restate the codebase back.
- If a step needs a paragraph to explain, it belongs in an issue, not in
  the plan.

## Enough

Plans are approved in conversation rather than committed, so there is no
colleague-written example to copy. The following is constructed.

> **Open:** should a file on an unrecognized grid be regridded when the
> user supplies its grid, or stay an error?
>
> 1. Add `--source-grid`, taking a CDO grid description file.
> 2. Use it only for a file whose grid matches no ISMIP7 grid.
> 3. Cache its weights under a name taken from the file's contents.
> 4. Add the option to the running page.
