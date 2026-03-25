# Agentics Plan — overlapmap

Add [GitHub Agentic Workflows](https://github.com/githubnext/agentics) to the LA County neighborhood scorer.

## Prerequisites

```bash
gh extension install github/gh-aw
```

## Workflows to Add

- [ ] **Daily Accessibility Review** — runs the web app and reviews accessibility; critical for a public-facing interactive map
  ```bash
  gh aw add-wizard githubnext/agentics/daily-accessibility-review
  ```

- [ ] **Multi-Device Docs Tester** — tests the map UI across mobile, tablet, and desktop viewports
  ```bash
  gh aw add-wizard githubnext/agentics/daily-multi-device-docs-tester
  ```

- [ ] **Daily Adhoc QA** — explorative QA on geo filters, scoring edge cases, and layer interactions
  ```bash
  gh aw add-wizard githubnext/agentics/daily-qa
  ```

- [ ] **Link Checker** — validates data source URLs (crime APIs, school APIs, transit feeds, etc.)
  ```bash
  gh aw add-wizard githubnext/agentics/link-checker
  ```

- [ ] **Daily Perf Improver** — LA geo queries can be slow; surfaces benchmarking opportunities
  ```bash
  gh aw add-wizard githubnext/agentics/daily-perf-improver
  ```

- [ ] **Daily Malicious Code Scan** — scans for supply-chain risks in Python/data deps
  ```bash
  gh aw add-wizard githubnext/agentics/daily-malicious-code-scan
  ```

- [ ] **Issue Triage** — auto-labels incoming issues and PRs
  ```bash
  gh aw add-wizard githubnext/agentics/issue-triage
  ```

- [ ] **Plan** (`/plan` command) — breaks big issues into tracked sub-tasks
  ```bash
  gh aw add-wizard githubnext/agentics/plan
  ```

## Keep Workflows Updated

```bash
gh aw upgrade
gh aw update
```
