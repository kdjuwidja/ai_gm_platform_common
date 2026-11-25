# ai_gm_platform_common

`shared`, the ai_gm platform's Python package (workspace ADR 001): the code every service on the
platform uses, whatever its product. It is imported as `shared` and distributed as `ai-gm-shared`,
released by this repository's own git tags.

It moved here from `ai_gm_platform/shared/` under
[workspace ADR 001](https://github.com/kdjuwidja/ai_gm_workspace/blob/main/docs/adr/001-platform-split.md),
so that `ai_gm_platform`'s tags stay its own deployment releases.

| Module | What it holds |
|---|---|
| `auth.py` | Verifying an OAuth access token (HS256, the required scopes), giving the player's `sub` |
| `deps.py` | FastAPI dependencies: the caller, their roles (creator, admin), service outcomes → HTTP codes |
| `errors.py` | The outcomes a service reports (`NotFound`, `Conflict`, `Invalid`, `Forbidden`, `PaymentRequired`, `Unavailable`) |
| `roles.py` | The role names and the display name on a player's record |
| `internal_auth.py` | The receiving end of the service token on `/internal/` routes |
| `internal_client.py` | The calling end: an HTTP client that sends the service token |
| `lease_store.py`, `leased_job.py` | Short exclusive leases in MongoDB, and a job that runs only in the process holding its lease |
| `access_log.py` | The uvicorn access-log filter that leaves out the repeated successful requests |

## What belongs here
- Code that at least two services use and that knows nothing about any one product.
- Nothing of a product's: no game rule, ruleset, content limit or product name. Nightshade's own shared
  code is `nightshade-common/` in `ai_gm_nightshade` (the campaign word limits are there).
- Nothing that imports a service's own modules. A service depends on `shared`, never the other way round.

## Using it
A service — hub-service in `ai_gm_platform` as much as a product's — depends on a tag, and its
`uv.lock` pins the commit:

```toml
dependencies = ["ai-gm-shared"]

[tool.uv.sources]
ai-gm-shared = { git = "https://github.com/kdjuwidja/ai_gm_platform_common", tag = "v1.0.0" }
```

This repository is public, so installing it needs no credentials: no token or SSH key, and no build
secret in a service's Docker build.

While developing against an unreleased change, check this repository out beside the service's
repository. The paths below are from that sibling repository's root; a service in a subfolder adds one
`../` per level (from `ai_gm_platform/hub-service/`, it is `../../ai_gm_platform_common`):
- `uv run --with-editable ../ai_gm_platform_common pytest` runs a service's tests on the local copy;
- a service may point at the local copy for a while with
  `ai-gm-shared = { path = "../ai_gm_platform_common", editable = true }`, and returns to a tag before
  it merges;
- a branch may pin a branch or commit of this repository (`branch = "…"` or `rev = "…"` instead of
  `tag`) to try it in the stack, and returns to a tag before it merges.

## Releasing
1. Merge the change to `main` with its tests passing, and bump `version` in `pyproject.toml` (semantic
   versioning: a change that breaks a caller is a new major version).
2. Tag that commit in this repository `v<version>` (for example `v1.1.0`) and push the tag:
   `git tag v1.1.0 && git push origin v1.1.0`. A tag is never moved or reused.
3. Each service bumps its `tag` and runs `uv lock --upgrade-package ai-gm-shared` when it's ready.

## Tests
```sh
uv run pytest
```
`tests/test_leases.py` needs a throwaway MongoDB: set `SHARED_TEST_MONGO_URI` (skipped otherwise).
