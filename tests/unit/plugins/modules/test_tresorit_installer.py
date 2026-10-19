"""The installer check, run by the real ansible-playbook against installers signed by a CA made for the test."""

import datetime
import json
import os
import subprocess
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

PLAY = Path(__file__).parent / "plays" / "installer.yml"
NOW = datetime.datetime.now(datetime.timezone.utc)
PAYLOAD = b"SKIP=5\nCHECKSUM=1\necho installing\n\x1f\x8b\x08 archive bytes \x00\xff\n"


def name(common_name):
    return x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "HU"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Test Kft."),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ]
    )


def key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def ca(common_name):
    """A CA that may sign leaves only, as Tresorit's Code Signing CA 2020."""
    private = key()
    cert = (
        x509.CertificateBuilder()
        .subject_name(name(common_name))
        .issuer_name(name(common_name))
        .public_key(private.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(NOW - datetime.timedelta(days=1))
        .not_valid_after(NOW + datetime.timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.KeyUsage(False, False, False, False, False, True, True, False, False), critical=True)
        .sign(private, hashes.SHA512())
    )
    return private, cert


def leaf(issuer_key, issuer, usage=ExtendedKeyUsageOID.CODE_SIGNING, days=365):
    private = key()
    cert = (
        x509.CertificateBuilder()
        .subject_name(name("Test for Linux Code Signing Certificate"))
        .issuer_name(issuer.subject)
        .public_key(private.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(NOW - datetime.timedelta(days=2))
        .not_valid_after(NOW + datetime.timedelta(days=days))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.ExtendedKeyUsage([usage]), critical=True)
        .sign(issuer_key, hashes.SHA512())
    )
    return private, cert


def fingerprint(cert):
    return ":".join(f"{byte:02X}" for byte in cert.fingerprint(hashes.SHA256()))


def pem(cert):
    return cert.public_bytes(serialization.Encoding.PEM).decode()


def installer(signer, chain, payload=PAYLOAD):
    """An installer laid out as Tresorit's: line 2 the signature over everything from line 3 on, line 3 the chain."""
    signed = ('CERT_CHAIN="' + "".join(pem(cert) for cert in chain).replace("\n", "\\n") + '"\n').encode() + payload
    signature = signer.sign(
        signed, padding.PSS(mgf=padding.MGF1(hashes.SHA512()), salt_length=padding.PSS.DIGEST_LENGTH), hashes.SHA512()
    )
    return b"#!/bin/sh\nSIGNATURE=" + signature.hex().encode() + b"\n" + signed


def check(tmp_path, content, pinned):
    """Runs the module on an installer with the given content and returns its result."""
    path = tmp_path / "tresorit_installer.run"
    path.write_bytes(content)
    result = tmp_path / "result.json"
    done = subprocess.run(
        [
            "ansible-playbook",
            "-i",
            "localhost,",
            str(PLAY),
            "-e",
            json.dumps({"installer": str(path), "ca_sha256": pinned, "result": str(result)}),
        ],
        env=dict(os.environ, ANSIBLE_NOCOLOR="1"),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.exists(), done.stdout + done.stderr
    return json.loads(result.read_text())


@pytest.fixture(scope="module")
def pinned():
    return ca("Test Code Signing CA 2020")


def test_an_installer_signed_under_the_pinned_ca_passes(tmp_path, pinned):
    ca_key, ca_cert = pinned
    signer, cert = leaf(ca_key, ca_cert)
    result = check(tmp_path, installer(signer, [cert, ca_cert]), fingerprint(ca_cert))
    assert not result.get("failed"), result
    assert result["changed"] is False
    assert result["signer"] == "Test for Linux Code Signing Certificate"


def test_the_pin_is_read_in_any_case_and_with_or_without_colons(tmp_path, pinned):
    ca_key, ca_cert = pinned
    signer, cert = leaf(ca_key, ca_cert)
    result = check(tmp_path, installer(signer, [cert, ca_cert]), fingerprint(ca_cert).replace(":", "").lower())
    assert not result.get("failed"), result


def test_one_changed_byte_anywhere_after_the_signature_is_refused(tmp_path, pinned):
    ca_key, ca_cert = pinned
    signer, cert = leaf(ca_key, ca_cert)
    content = bytearray(installer(signer, [cert, ca_cert]))
    content[-3] ^= 0x01
    result = check(tmp_path, bytes(content), fingerprint(ca_cert))
    assert result["failed"] and "signature" in result["msg"], result


def test_a_chain_under_another_ca_is_refused_though_it_signs_correctly(tmp_path, pinned):
    _, pinned_cert = pinned
    other_key, other_cert = ca("Test Code Signing CA 2020")
    signer, cert = leaf(other_key, other_cert)
    result = check(tmp_path, installer(signer, [cert, other_cert]), fingerprint(pinned_cert))
    assert result["failed"] and "pinned" in result["msg"], result


def test_the_pinned_ca_beside_a_leaf_it_did_not_sign_is_refused(tmp_path, pinned):
    _, ca_cert = pinned
    other_key, other_cert = ca("Test Code Signing CA 2020")
    signer, cert = leaf(other_key, other_cert)
    result = check(tmp_path, installer(signer, [cert, ca_cert]), fingerprint(ca_cert))
    assert result["failed"] and "issued" in result["msg"], result


def test_a_leaf_not_made_for_code_signing_is_refused(tmp_path, pinned):
    ca_key, ca_cert = pinned
    signer, cert = leaf(ca_key, ca_cert, usage=ExtendedKeyUsageOID.SERVER_AUTH)
    result = check(tmp_path, installer(signer, [cert, ca_cert]), fingerprint(ca_cert))
    assert result["failed"] and "code signing" in result["msg"], result


def test_an_expired_leaf_is_refused(tmp_path, pinned):
    ca_key, ca_cert = pinned
    signer, cert = leaf(ca_key, ca_cert, days=-1)
    result = check(tmp_path, installer(signer, [cert, ca_cert]), fingerprint(ca_cert))
    assert result["failed"] and "valid" in result["msg"], result


def test_a_file_without_the_signature_lines_is_refused(tmp_path, pinned):
    _, ca_cert = pinned
    result = check(tmp_path, b"#!/bin/sh\necho installing\n", fingerprint(ca_cert))
    assert result["failed"] and "SIGNATURE" in result["msg"], result
