# ai_gm_platform_common

`shared`, the Python package every ai_gm service uses (token checks, the service token on `/internal/`,
errors, roles, leases, the access-log filter), distributed as `ai-gm-shared` and released by this
repository's own git tags.

It is moving here from `ai_gm_platform/shared/` under
[workspace ADR 001](https://github.com/kdjuwidja/ai_gm_workspace/blob/main/docs/adr/001-platform-split.md),
so that `ai_gm_platform`'s tags stay its own deployment releases.
