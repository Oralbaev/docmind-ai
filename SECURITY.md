
# Security Policy

## Project Security

DocMind AI follows a shift-left security approach.

Security checks are performed locally and in CI/CD
before changes are merged into the main branch.

## Security Controls

| Control | Tool | Execution |
|---|---|---|
| SAST | Semgrep | Pre-commit and GitHub Actions |
| SCA | Trivy | GitHub Actions |
| Secret Scanning | Trivy | GitHub Actions |
| Dependency Validation | pip check | Local validation |
| SBOM | Trivy | Local generation |

## Secure Development Rules

1. Never commit API keys, passwords, or .env files.
2. Validate untrusted user input.
3. Use parameterized SQL queries.
4. Verify authorization before accessing user resources.
5. Review dependency changes for known vulnerabilities.
6. Do not merge changes with failed security checks.
7. Keep security tools separate from application dependencies.

## Vulnerability Management

When a vulnerability is found:

1. Identify the affected file or dependency.
2. Assess severity and exploitability.
3. Determine whether the application is affected.
4. Apply a fix or document an accepted risk.
5. Run SAST and SCA again.
6. Record the result in the security audit.

## Reporting Vulnerabilities

Do not disclose API keys, passwords, or exploit details
in public GitHub issues.

Use GitHub's private vulnerability reporting feature
if it is enabled for this repository.

## Security Dashboard

See [Security Overview](security/README.md).

## Current Audit

See the Security Overview for the dated baseline results.
Historical findings do not guarantee current security.
