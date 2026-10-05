# ADR-005: Cells: scale workers by adding independent units

- Status: accepted
- Date: 2026-10-05

## Context

One Redis and one dispatcher cannot serve an unlimited number of workers, and one failure should
not stop every customer.

## Decision

A cell is one Redis plus its workers and control process. Each tenant is mapped to one cell in
`tenant_cells`; moving a tenant is a data change. Redis keys use `{tenant}` hash tags so a cell can
become a Redis Cluster later.

## Consequences

- Horizontal scale and fault isolation without code changes.
- A tenant larger than one cell needs the cell itself to scale (Redis Cluster, more workers).
