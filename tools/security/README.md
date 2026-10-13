# Free local supply-chain evidence

Run `python -m tools.security.assurance tools/security/assurance.json` using a Python installation
with Pydantic. Configure a checksum-verified native Trivy executable for the host platform. The
tool copies only explicit lockfiles, emits CycloneDX inventory and a vulnerability report including
development dependencies, and fails visibly on scanner errors/findings/timeouts. No paid service
or cloud account is used. Scan the final Docker image separately with native Docker access:

```sh
trivy image --image-src docker --scanners vuln --severity HIGH,CRITICAL --exit-code 1 \
  --format json --output image.json IMAGE_TAG
```

The source provenance manifest hashes allowed source roots and excludes private/generated trees,
environment files and private keys. Hash inventory alone is unsigned. To attest exact bytes with
an operator-controlled offline Ed25519 key, record it in the private ignored recovery inventory,
store the private key in an ignored path, and distribute its public verification key separately:

```sh
python -m tools.security.signing sign provenance.json PRIVATE_KEY_FILE provenance.sig
python -m tools.security.signing verify provenance.json PUBLIC_KEY_FILE provenance.sig
```

`sign` refuses a private key that Git does not ignore. The verification key must come from a
trusted channel; accepting an attacker-supplied key alongside an artifact proves nothing about
the signer. Signature tests reject changed payloads and wrong signers. This local signature is
not independent identity certification or a SLSA provenance claim. Sign only after the final
manifest/build inputs are fixed; modifying signed bytes invalidates the signature.

Official tool guidance: [Trivy filesystem](https://trivy.dev/docs/latest/target/filesystem/),
[Trivy image](https://trivy.dev/docs/latest/target/container_image/).

## Exact artifact and runtime gates

For final release directory signing and complete-file-list verification, use the dedicated
[artifact workflow](release-artifacts.md), not the generic source-hash signature alone. Bind native
application and web image identities/SBOMs to the final signed inventory. Local and server builds
may have different IDs; attest the actual deployment images and verify them again after startup.

Retain findings and failed attempts. A zero HIGH/CRITICAL vulnerability scan is a point-in-time
scanner result, not proof of complete security or ASVS certification. Separate production images,
source dependencies and development-tool advisories. See [security controls](../../docs/security/controls.md),
[maintenance](../../docs/maintenance.md) and [release procedure](../../docs/operations/deployment.md).
