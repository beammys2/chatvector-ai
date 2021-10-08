# Releasing `@chatvector/sdk`

This document covers maintainer steps to publish the TypeScript SDK to npm.
Pull-request CI validates type-check, unit tests, build, and `npm pack` smoke
tests on Node 22 and 24; publishing is a separate, protected release workflow.

## Prerequisites (maintainer checklist)

Before the first public release, confirm:

1. **npm organization access** — a maintainer controls the `@chatvector` npm
   scope and can publish `@chatvector/sdk` with public access.
2. **GitHub secret** — add `NPM_TOKEN` to the upstream repository secrets with
   an npm automation or granular publish token scoped to the `@chatvector` org.
3. **Provenance** — the publish workflow uses npm provenance (`publishConfig`
   in `package.json`). The token must allow provenance attestation.

If the scope is unavailable, do not publish under an unscoped fallback name
without an explicit maintainer decision (see `DESIGN.md`).

## Semver policy (pre-1.0)

While the major version is `0`, this package follows pre-1.0 semver:

| Bump | When |
| --- | --- |
| `0.x.Y` patch | Bug fixes and internal changes that do not alter the documented public API |
| `0.Y.0` minor | New backward-compatible public API surface |
| Breaking change | Bump the minor version (`0.Y.0`), not patch — e.g. `0.1.x` → `0.2.0` |

Document breaking changes in the GitHub release notes. After `1.0.0`, follow
standard semver (major for breaking changes).

Tag names must match the published version: `sdk-typescript-v{version}` (for
example `sdk-typescript-v0.1.0`).

## Automated release (recommended)

1. Update `version` in `sdk/typescript/package.json` on `main`.
2. Commit the version bump (for example `[448] release @chatvector/sdk 0.1.1`).
3. Create and push an annotated tag:

   ```bash
   git tag -a sdk-typescript-v0.1.1 -m "@chatvector/sdk 0.1.1"
   git push upstream sdk-typescript-v0.1.1
   ```

4. The [npm publish workflow](../../.github/workflows/npm-publish.yml) runs on
   the tag, verifies the tag matches `package.json`, runs the full SDK test
   suite including `npm pack` export smoke tests, and publishes with
   `--access public --provenance`.
5. Create a GitHub release from the tag summarizing changes. The published npm
   version must match the tag suffix.

## Manual release (fallback)

Use this only when the GitHub workflow is unavailable:

```bash
cd sdk/typescript
npm ci
npm run type-check
npm run test:unit
npm run build
npm run test:exports
npm pack --dry-run   # inspect files, exports, and types
npm login            # or export NODE_AUTH_TOKEN for CI-style auth
npm publish --access public --provenance
git tag -a sdk-typescript-v$(node -p "require('./package.json').version") \
  -m "@chatvector/sdk $(node -p "require('./package.json').version")"
git push upstream --tags
```

The `prepublishOnly` script reruns type-check, unit tests, build, and export
tests before `npm publish`.

## Verify after publish

In a clean directory outside the monorepo:

```bash
npm install @chatvector/sdk@latest
node --input-type=module -e "import { ChatVectorClient } from '@chatvector/sdk'; console.log(typeof ChatVectorClient)"
```

Confirm the browser export still throws a server-only error:

```bash
node --conditions=browser --input-type=module -e "import('@chatvector/sdk')"
```

Expected: an error message mentioning server-only / browser guard — not a
successful import.
