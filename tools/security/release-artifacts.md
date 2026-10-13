# Exact release signature verification

`release_artifacts.py` signs the final release's exact primary files with an independently retained
Ed25519 key. This adds a signer identity to SHA-256 inventory checks. It is a local owner attestation,
not a third-party identity certificate, reproducible-build guarantee or SLSA certification.

## Build and sign

The central `ReleaseSigningSettings` owns the private key path, trusted public key path and key ID.
Set the `FW_RELEASE_SIGNING__*` variables from the environment template. The private key must be
outside the artifact directory and Git-ignored before the CLI permits signing. Its public counterpart
must match; this tool does not generate or rotate keys. Keep actual private recovery material only
in the ignored credentials inventory and a separate protected backup.

1. Freeze and build the reviewed release using the normal release builder. Its existing manifest
   must already match every primary file. New, missing or modified files stop signing.
2. Build and rehearse the exact release source archive. Inspect both final application and web
   images' immutable `sha256:` IDs or repository digests. Generate native CycloneDX SBOMs for the
   images being deployed. Application and web identities are different and must not be swapped.
3. Sign the final artifact directory, then verify it using the separately retained trust anchor:

```sh
uv run python -m tools.security.release_artifacts sign RELEASE_DIRECTORY \
  --image-identity sha256:INSPECTED_FINAL_IMAGE_DIGEST --sbom FINAL_IMAGE_SBOM.json
uv run python -m tools.security.release_artifacts verify RELEASE_DIRECTORY
```

The digest placeholder above must be replaced by the actual inspected SHA-256 value. Both image
identity and SBOM arguments are optional: omit them when they are not verified, and do not claim
the resulting signature attests an image. They are public metadata, not credential arguments.
Signing checks the initial manifest and configured key pair before adding any files. A signed or
partially finalized release cannot be overwritten or silently re-signed; build a new immutable
release if its bytes need to change or finalization is interrupted.

4. Upload the exact finalized files and manifest; verify their parity. Verify the detached
   signature after fetching the release back or on a machine with the independently trusted key.
5. If the server builds the image separately, inspect and compare its actual immutable identity.
   Independent builds may differ. A signature that names the local image does not prove identity
   for a different server image. Transfer the exact inspected image when identical identity is
   required, or record the server image separately and state the distinction.

## Signed file relationships

The signed `PROVENANCE.json` records release ID, source commit, signer key ID, optional caller-
inspected immutable image identity, optional SBOM reference and every primary artifact SHA-256.
It also includes the bundled `RELEASE-SIGNING-PUBLIC.pem` hash. The Ed25519 detached signature is
`PROVENANCE.sig`.

Provenance excludes only `MANIFEST.sha256`, itself and its signature, which avoids circular hashes.
The final manifest covers every file except itself, including provenance, detached signature,
bundled public key and any copied `SBOM.cdx.json`. Metadata contains no private key or local secret
paths. The verification key inside the release is convenience data: verification refuses to use
it as its own trust anchor.

Verification checks the signature against the separately trusted configured public key, matches
the bundled key to that anchor, checks source commit/release ID against `RELEASE.json`, validates
optional image/SBOM references, and recomputes every artifact hash and the complete file list.
It rejects missing files, unlisted files, duplicate/unsafe manifest paths, symlinks, changed
provenance/signatures and noncanonical or altered manifests. A valid hash manifest alone cannot
authorize changed artifact bytes because the separately signed inventory must also match.

The tool attests the bytes and metadata supplied by the release workflow. It does not establish
that a Git commit actually produced an image, that a scanner report is complete, that an artifact
contains no secrets, or that the deployed runtime still matches it. Those remain separate build,
security, rehearsal and deployment parity gates.

## Native application and web image binding

The final release records the native application identity/SBOM in provenance and includes the
separately prepared `WEB-IMAGE.json` and `WEB-SBOM.cdx.json` as signed primary artifacts. Verify
the complete release against the independent trust anchor before reading either identity as
approved deployment input. An unsigned image record or a rewritten hash list is insufficient.

Compare backend roles against the application identity and the web role against the web identity
immediately before startup, then compare running containers afterward. A tag can be reassigned;
its inspected immutable identity must match. Preserve native scan reports and reject a mismatched
or substituted image even if another image from the same source passed its scan.

An independently rebuilt image can differ from a local image. Record and scan the actual server
image rather than claiming binary parity from source parity. Signed metadata establishes the
operator's attestation of exact supplied bytes, not independent build reproducibility or security
certification. See [deployment](../../docs/operations/deployment.md) for all-worker drain and
compatibility-aware rollout/rollback.

For namespace-package type checks use:

```sh
uv run mypy --explicit-package-bases tools/security/release_artifacts.py
uv run pytest tools/security/tests/test_release_artifacts.py
```

Official cryptographic reference: [pyca/cryptography Ed25519](https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/).
