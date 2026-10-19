# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Checks Tresorit's Linux installer against a pinned CA before anything of it runs."""

from __future__ import annotations

DOCUMENTATION = r"""
module: tresorit_installer
short_description: Check Tresorit's Linux installer against a pinned CA
description:
  - Reads the installer's line 2, C(SIGNATURE=), and line 3, C(CERT_CHAIN=), without running anything of the file.
  - Passes only when the chain holds the pinned CA, the CA issued the chain's first certificate, that certificate is
    made for code signing and valid now, and its key's RSASSA-PSS SHA-512 signature covers everything from line 3 on.
  - The installer's own C(CHECKSUM) is a CRC against accidents, which this check does not lean on.
  - Changes nothing; check mode runs it alike.
options:
  path:
    description: The downloaded installer.
    type: path
    required: true
  ca_sha256:
    description: The SHA-256 fingerprint of the CA that issues Tresorit's Linux signing certificate, colons optional.
    type: str
    required: true
requirements:
  - python3-cryptography 40 or later, which Ubuntu's ansible-core depends on.
"""

RETURN = r"""
signer:
  description: The common name of the certificate whose key signed the installer.
  type: str
  returned: success
not_after:
  description: Until when that certificate is valid, in ISO 8601.
  type: str
  returned: success
sha256:
  description: The installer's SHA-256 digest, for the log.
  type: str
  returned: success
"""

import datetime
import hashlib
import re

from ansible.module_utils.basic import AnsibleModule

try:
    from cryptography import x509
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
except ImportError:  # pragma: no cover - reported to the caller below
    x509 = None


class Refused(Exception):
    """The installer is not the one the pinned CA vouches for."""


def header(content):
    """Splits the file into its signature, its chain and the bytes the signature covers."""
    first = content.find(b"\n") + 1
    second = content.find(b"\n", first) + 1
    signature_line = content[first : second - 1] if second > first else b""
    if not first or not second or not signature_line.startswith(b"SIGNATURE="):
        raise Refused("line 2 is not SIGNATURE=<hex>, so this is no installer Tresorit signed")
    third = content.find(b"\n", second) + 1
    chain_line = content[second : third - 1] if third > second else b""
    if not third or not chain_line.startswith(b'CERT_CHAIN="') or not chain_line.endswith(b'"'):
        raise Refused('line 3 is not CERT_CHAIN="<certificates>", so this is no installer Tresorit signed')
    try:
        signature = bytes.fromhex(signature_line[len(b"SIGNATURE=") :].decode("ascii"))
    except ValueError as error:
        raise Refused(f"line 2's SIGNATURE is not hex: {error}") from error
    chain = chain_line[len(b'CERT_CHAIN="') : -1].replace(b"\\n", b"\n")
    try:
        certificates = x509.load_pem_x509_certificates(chain)
    except ValueError as error:
        raise Refused(f"line 3's CERT_CHAIN holds no readable certificates: {error}") from error
    return signature, certificates, content[second:]


def common_name(certificate):
    names = certificate.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
    return names[0].value if names else certificate.subject.rfc4514_string()


def check(content, ca_sha256, now):
    """Returns the signing certificate when the installer passes; raises Refused naming why it does not."""
    signature, certificates, signed = header(content)
    signing, rest = certificates[0], certificates[1:]
    pinned = [cert for cert in rest if cert.fingerprint(hashes.SHA256()).hex() == ca_sha256]
    if not pinned:
        raise Refused(f"the chain holds no CA with the pinned fingerprint {ca_sha256}")
    try:
        signing.verify_directly_issued_by(pinned[0])
    except (ValueError, TypeError, InvalidSignature) as error:
        raise Refused(f"'{common_name(signing)}' was not issued by the pinned CA '{common_name(pinned[0])}'") from error
    for cert in (signing, pinned[0]):
        if not cert.not_valid_before_utc <= now <= cert.not_valid_after_utc:
            raise Refused(
                f"'{common_name(cert)}' is valid from {cert.not_valid_before_utc} to {cert.not_valid_after_utc} only"
            )
    try:
        usages = signing.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
    except x509.ExtensionNotFound:
        usages = []
    if ExtendedKeyUsageOID.CODE_SIGNING not in usages:
        raise Refused(f"'{common_name(signing)}' is not made for code signing")
    try:
        signing.public_key().verify(
            signature,
            signed,
            padding.PSS(mgf=padding.MGF1(hashes.SHA512()), salt_length=padding.PSS.DIGEST_LENGTH),
            hashes.SHA512(),
        )
    except InvalidSignature as error:
        raise Refused(f"the signature of '{common_name(signing)}' does not cover this file as it is") from error
    return signing


def main():
    module = AnsibleModule(
        argument_spec={
            "path": {"type": "path", "required": True},
            "ca_sha256": {"type": "str", "required": True},
        },
        supports_check_mode=True,
    )
    if x509 is None:
        module.fail_json(msg="python3-cryptography is missing, which Ubuntu's ansible-core depends on")
    ca_sha256 = re.sub(r"[:\s]", "", module.params["ca_sha256"]).lower()
    if not re.fullmatch(r"[0-9a-f]{64}", ca_sha256):
        module.fail_json(msg=f"ca_sha256 is no SHA-256 fingerprint: {module.params['ca_sha256']}")
    try:
        with open(module.params["path"], "rb") as installer:
            content = installer.read()
    except OSError as error:
        module.fail_json(msg=f"could not read {module.params['path']}: {error}")
    try:
        signing = check(content, ca_sha256, datetime.datetime.now(datetime.timezone.utc))
    except Refused as error:
        module.fail_json(msg=f"REFUSED {module.params['path']}: {error}")
    module.exit_json(
        changed=False,
        signer=common_name(signing),
        not_after=signing.not_valid_after_utc.isoformat(),
        sha256=hashlib.sha256(content).hexdigest(),
    )


if __name__ == "__main__":
    main()
