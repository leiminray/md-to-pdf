<!--
Thanks for the PR. The acceptance gate (CI workflow `acceptance.yml`) is
required to pass before merge. The checklist below mirrors what the gate
checks — if you've covered it, the gate should be green; if any item is
unanswered, expect a red CI.
-->

## Summary

<!-- 1-3 bullets describing what changed and why -->

## Spec & acceptance

- [ ] If this PR touches `docs/superpowers/specs/*.md`, I also updated
      `docs/acceptance/*.yaml` to match (fixtures, deterministic targets,
      extras, brand minimum). The audit's spec-drift check enforces this.
- [ ] If this PR adds a fixture, I also added the four golden baselines
      (ast / text_layer / xmp / layout_fingerprint). Strict-golden CI fails
      if any layer is missing.
- [ ] If this PR adds a `pyproject.toml` extras name, I also listed it in
      `acceptance.yaml` `extras_matrix.required`.

## Verification

- [ ] `pytest` passes locally
- [ ] `python scripts/check_acceptance.py --skip-pytest` exits 0 locally
      (or the failures are intentional and called out below)

## Notes

<!-- anything reviewers should know that isn't obvious from the diff -->
