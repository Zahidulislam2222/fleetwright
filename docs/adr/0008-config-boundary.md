# ADR-008: One typed configuration boundary; product data in YAML

- Status: accepted
- Date: 2026-10-05

## Context

Hardcoded URLs, timeouts and limits make every environment change a code change and leak
infrastructure details into source control.

## Decision

All settings come from `fw_core.settings` (Pydantic settings, environment variables,
`.env.example` documents every variable). Product data such as targets, browser profiles, proxies and
the demo catalogue lives in validated YAML in `config/`. A test fails if a URL or secret pattern
appears in business code.

## Consequences

- Local → single server → AWS by changing configuration only.
- New settings must be added in two places (settings model and `.env.example`); a test enforces it.
