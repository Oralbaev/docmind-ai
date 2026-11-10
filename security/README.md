
# Lab 7 — Security Code Review

## Project
DocMind AI — Python/FastAPI backend.

## Security Tools
- Semgrep 1.184.0 — SAST
- Trivy 0.76.2 — SCA and Secret Scanning
- GitHub Actions — CI/CD

## Quick Access

| Resource | Link |
|---|---|
| CI/CD Security Checks | [GitHub Actions](https://github.com/Oralbaev/docmind-ai/actions/workflows/security.yml) |
| Security Policy | [SECURITY.md](../SECURITY.md) |
| Security Audit PR | [Pull Request #1](https://github.com/Oralbaev/docmind-ai/pull/1) |

## Security Baseline

| Check | Last recorded result |
|---|---|
| SAST | 0 findings |
| SCA (isolated Python environment) | 0 known CVEs |
| Secret Scanning | 0 findings in scanned files |
| Dependency Integrity | No conflicts |
| SBOM | CycloneDX 1.7, 99 components |

These are historical audit results, not live status indicators.
Use GitHub Actions for the latest CI results.

## SAST Results
- 31 Git-tracked files scanned
- 200 rules executed
- 0 findings

## SCA Results
- Initial development environment: 5 MEDIUM findings
- Isolated application environment: 0 findings
- Dependency integrity: no conflicts

The initial findings were associated with packages
introduced by development/security tooling.

## Secret Scanning
- 0 findings in scanned files
- Local .env excluded
- .env ignored by Git

## SBOM
- Format: CycloneDX 1.7
- Components: 99
- Vulnerabilities reported: 0

## CI/CD
Three automated checks:
1. Semgrep SAST
2. Trivy SCA
3. Trivy Secret Scanning

## Limitations
- Automated scanners cannot detect every vulnerability.
- Community SAST rules have limited coverage.
- Local secrets were excluded from scanning.
- The SBOM covers Python dependencies only.
- SCA in CI blocks HIGH and CRITICAL findings.

## Peer Review
- Reviewer: Pending
- Status: Pending
- Approval: Pending
