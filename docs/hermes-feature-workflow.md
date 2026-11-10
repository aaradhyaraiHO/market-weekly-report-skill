# Hermes Feature Workflow

This documentation-only workflow defines the lifecycle for a Hermes feature request. It does not authorize changes to code, configuration, buckets, formulas, metrics, or deployment behavior.

## Workflow

1. Receive the request and define its exact scope.
2. Prepare a complete, minimal implementation plan, including the approved paths, intended behavior, and scoped local tests.
3. Obtain Aaradhya's explicit approval of the plan. Implementation must not begin before that approval.
4. Perform the implementation in isolation and run the scoped local tests, changing only what the approved plan permits.
5. Open a draft PR. The workflow ends at the draft PR; creating it does not authorize merge or deployment.

If implementation would require any scope expansion, first update the plan and obtain Aaradhya's explicit approval of the updated plan. Do not implement the expanded scope before approval.

## Isolation Requirements

- Change only the paths and behavior explicitly included in the approved plan.
- Avoid unrelated edits, cleanup, refactoring, or behavior changes.
- Run only scoped local tests relevant to the approved work.
- Do not publish artifacts or perform a deployment as part of this workflow.

## Approval Boundaries

Plan approval authorizes only the isolated implementation and tests described in the approved plan. It does not authorize merge or deployment.

Merge requires separate approval that is explicit; neither plan approval nor implementation approval grants merge approval.

Deployment requires separate approval that is explicit; plan approval, implementation approval, creation of a draft PR, and merge approval do not grant deployment approval.
