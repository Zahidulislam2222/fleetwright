# ADR-009: What "1M users" and "99% uptime" mean here

- Status: accepted
- Date: 2026-10-05

## Context

The owner asked for a design that can serve 1M+ simultaneous users with at least 99% uptime.
Fleetwright's users are operators; a million connected sessions only exists as a multi-tenant SaaS.
A million browser sessions would need about 100 TB of RAM, which is a different problem.

## Decision

The control plane (API, console, live updates) is designed for 1M concurrent connected sessions
across many tenants. The worker plane is designed to grow by cells from tens to 10,000+ workers. The
availability target for the cloud reference is **99.9%** per month (stricter than the 99% asked for).
Nothing beyond what was measured is claimed as achieved.

## Consequences

- The scaling docs separate *measured* from *target* numbers.
- The current single-server demo cannot meet either target and says so.
