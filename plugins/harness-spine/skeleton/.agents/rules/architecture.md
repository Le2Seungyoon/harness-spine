# Architecture

## Layers & dependency direction

```
<!-- FILL: layer diagram, e.g.  config → data/io → domain → interface -->
```

- **Lower layers never import higher ones.** State the dependency arrows explicitly.
<!-- FILL: how modules are accessed (package import? path?), and the entry points. -->

## Shared homes (where a second occurrence gets promoted to)

`coding-patterns.md` → When to extract says the second copy must be promoted. It can only be
obeyed if there is somewhere to promote it **to**. Name that place per kind of thing:

| Kind of thing | Shared home |
|---------------|-------------|
<!-- FILL: one row per kind that gets repeated in this project — UI component / query / handler /
validator / pipeline node / report. Give the directory or module that owns it, and who may import
it. A kind with no home listed here is the case that gets copied instead of extracted. -->

If a kind has no home yet, **creating the home is part of the change that needed it** — not a
follow-up ticket. A promotion deferred to a later PR is a copy that ships.

## Module boundary contracts

<!-- FILL: for each boundary that must NOT be crossed by a direct import, name the contract that
replaces it (a registry, a queue, a shared config, an interface). Shape:
- `<producer>` and `<consumer>` never import each other — `<the contract>` is the only touchpoint.
-->

**A ban on direct module-to-module imports never bans going through a shared home.** Both callers
depending on one shared module is the intended resolution of a boundary rule, not a violation of
it — read a "no direct import" rule as prohibiting the *shortcut*, never the *extraction*.

## Idempotency (if applicable)

- If writes must be safe to re-run (retries / backfills), make them UPSERT-by-key so the same input
  yields the same result. <!-- FILL: state the actual write path + keys, or delete if N/A. -->

## CLI / logic separation

- Keep logic functions free of argument parsing; put the CLI (argparse / click / …) in a thin
  wrapper so the same function is callable from a notebook · CLI · scheduler without rewriting.
  <!-- FILL: adjust or delete to match this project. -->
