# Encrypted off-host recovery

The existing server creates verified PostgreSQL custom-format archives. Fleetwright's recovery
module copies an archive set to the operator PC, validates its manifest and hashes, and encrypts it
under a separate recovery master key. Keeping both the only archive and its only key on the
production server would leave a single-host failure unrecoverable.

## Recovery boundary

`RecoverySettings` owns the encrypted-bundle directory, maximum plaintext archive size, retention,
master key and key identifier. Configure these through the `FW_RECOVERY__*` environment variables.
Generate an independent 32-byte random recovery key; do not reuse the session-vault key. Actual
key values and private recovery procedures belong in the ignored credentials inventory, never in
source, this document, logs or public releases. Preserve the key separately from the encrypted
bundle. A lost key makes that bundle unusable.

Each archive set contains exactly its JSON manifest and the named `.dump` files. Validation
requires safe PostgreSQL database filenames, positive sizes, SHA-256 matches and PostgreSQL custom
archive signatures. Unexpected files, malformed manifests and oversized sets are rejected.

The module stores an authenticated envelope with a random data key and AES-GCM nonces, a wrapped
data key and format-bound associated data. It verifies the exact newly written ciphertext before
atomically publishing it or pruning old copies. Wrong keys, ciphertext changes, bad metadata,
compressed entries, duplicate ZIP entries and oversized expanded archives are rejected. Retention
keeps at least two completed copies. An invalid new archive never removes the last good copy.

The public Python entry points are `protect(settings, files)`, `open_bundle(settings, source)` and
`unpack(settings, source, destination)`. `unpack` requires a new destination directory and writes
only validated exact filenames with private permissions; it never extracts arbitrary ZIP paths.
Prefer restoring directly from `open_bundle` bytes to avoid plaintext archive files on disk.

## Safe restore procedure

1. Pull completed archives using the existing pinned SSH host key. Validate regular-file types,
   declared lengths and total size before accepting data, then compare every manifest SHA-256.
2. Encrypt on the independent machine and read the exact local ciphertext back through
   `open_bundle`. Preserve the preceding good copy until this verification succeeds.
3. Verify that the restore target is the local test database service. Create uniquely named fresh
   databases from `template0`; never reuse, drop or overwrite an existing database.
4. Restore with `pg_restore --exit-on-error --no-owner --no-privileges`. This tests data/schema
   recovery without copying production role ownership or privileges into the local environment.
5. Compare every restored public table's row count with the archive's COPY data counts. Include
   workflow jobs, approvals, events and grants in the evidence. Keep the archive hash and report.
6. For actual disaster recovery, recreate application roles and grants using the reviewed
   infrastructure/migrations, restore required independent vault/authentication keys, reconcile
   external outcomes, and verify tenant isolation and exact-action approvals before reopening
   mutating workflows. A data restore alone is not an application recovery proof.

## Verified observation

On 13 October 2026, read-only pinned SSH retrieval produced an authenticated encrypted off-host
bundle of 2,533,091 bytes. Restoring from its exact ciphertext created two fresh local databases:
20 Fleetwright and 8 mockboard public tables. All restored row counts matched the source archive's
COPY records. The archived workflow dataset recovered 4 jobs, 4 approvals, 20 events and 2 grants.
Plaintext archive files and SQL were kept in process memory. Existing production databases were
not modified or dropped. Tests additionally verified wrong-key/tamper refusal and preservation of
the last good copy after a rejected transfer.

This is an independent encrypted data-recovery drill using the existing infrastructure and local
tools. It is not proof of a second running site, multi-zone failover, a particular RPO/RTO or
complete loss-of-all-devices recovery. The archive contains encrypted application records; their
separate original application keys remain necessary. Rehearse the procedure periodically and
after schema/release changes, while preserving the last verified copy.

Official reference: [PostgreSQL pg_restore](https://www.postgresql.org/docs/current/app-pgrestore.html).
