# Testing

## Conventions

- Location & convention: `tests/<module>/test_*.py` (or this project's equivalent — match the
  existing tree). <!-- FILL: test layout + the run command. -->
- Deterministic, **no network access** in unit tests. Isolate external state (DB / services /
  tracking servers) in tmp dirs or fakes so no artifacts leak into the repo root.
  <!-- FILL: the project's isolation pattern + a reference test to copy. -->
- **No weak asserts**: checking only "within range" lets a wrong implementation pass. Verify exact
  values and relationships (distributions, invariants), not just bounds.
- Regression tests reproducing a gotcha come **with rationale** — a comment naming the bug they pin,
  so the assert isn't "mysteriously specific" to a future reader.

## Invariant tests (the layer hooks cannot reach)

A hook only sees edits made in an agent session. Code written in an IDE, by a teammate, or by
another agent never passes one. **A rule that must hold no matter who authored the code belongs
here**, as a test over the tree itself — not only as a hook (`enforcement.md` → Four layers).

- Assert the property, not the sample: walk the source tree and fail with the offending paths
  listed, so the message tells the reader what to fix.
- Give every invariant test an escape hatch the source can carry (a marker comment with a reason),
  or the first legitimate exception gets the test deleted.
- Shipped with the harness: `.agents/hooks/check_rule_links.py` pins that every file a rules
  file points at still exists — the pointers `workflow.md` -> File size budget tells you to leave
  behind; `.agents/hooks/test_harness_parity.py` pins that both harnesses register the same
  gates; `build-agents.py --check` is the freshness test for generated skill/lane copies. Wire
  all three into this project's suite or CI so they run on every authoring path.
  <!-- FILL: this project's invariant tests as they are added — what each pins, and its marker. -->

## Freshness tests for generated artifacts

Anything committed but generated (an inventory, a schema dump, a rule index) goes stale silently:
it rots through edits no hook observes. **Regenerate in the test and compare** — the test fails when
the committed copy is out of date, and the failure message names the regeneration command.

- **Prove it catches staleness by causing staleness**, three ways: delete one entry, delete a whole
  section, and add a real occurrence without regenerating. A freshness test that has never been
  seen red is a comment.
- **Name the authoring paths it still does not cover**, in the test's docstring. Being honest about
  the gap is what keeps someone from reading green as "nothing is stale anywhere".

## Verifying the defenses themselves

- **Delete the defense and re-run.** A passing suite is not evidence that a guard works — only that
  nothing currently violates it. Remove the check (or feed it a violating input) and confirm a test
  actually goes red. An untested guard is indistinguishable from a comment.
- **Fixtures must be distinguishable.** If two code paths coincidentally produce the same value, one
  output collapses both and a broken path still passes. Choose fixture values that differ per path,
  per branch, and per field being asserted.
