# Security Policy

## Supported versions

Only the latest released version of `skillpod` receives security fixes during
the 0.x series. Once 1.0.0 ships the policy will be revisited.

| Version | Supported |
| --- | --- |
| 0.5.x   | ✅ |
| < 0.5   | ❌ |

## Reporting a vulnerability

**Please do not file a public GitHub issue for security problems.**

Use one of the following private channels instead:

1. **GitHub Security Advisories** — preferred. Open a draft advisory at
   <https://github.com/g761007/skillpod-cli/security/advisories/new>.
2. Email the maintainer at **a761007@gmail.com** with the subject
   `[skillpod security]`.

Please include:

- A description of the issue and its impact.
- Steps to reproduce, or a proof-of-concept.
- The version (`skillpod --version` or commit SHA) you tested.
- Any suggested mitigation, if known.

## Response targets

- **Acknowledgement**: within 5 business days.
- **Triage and severity assessment**: within 10 business days.
- **Fix or mitigation**: depends on severity; a status update will be sent
  every 14 days until resolution.

## Scope

In-scope:

- The `skillpod` CLI and its installation pipeline (manifest parsing,
  lockfile resolution, source fetching, install/fan-out, adapter layer).
- The PyPI distribution and its build/release workflow.
- Any third-party skill content the CLI fetches **only** when the issue lies
  in how skillpod handles or trusts that content (e.g. path traversal during
  install). Vulnerabilities in unrelated upstream skills should be reported
  to those skill authors.

Out of scope:

- Vulnerabilities in dependencies (please report upstream; we will pull in
  fixes once they land).
- Issues that require an attacker to already control the user's machine,
  shell, or filesystem.

Thank you for helping keep skillpod and its users safe.
