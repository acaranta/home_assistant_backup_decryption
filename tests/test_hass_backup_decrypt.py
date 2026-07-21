"""Tests for the Home Assistant backup decryption tool."""

import inspect
import sys
from pathlib import Path

import pytest
import securetar

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import hass_backup_decrypt as hbd  # noqa: E402


SAMPLE_KEY = "ABCD-EFGH-IJKL-MNOP-QRST-UVWX-YZ01"


def test_password_to_key_length_and_determinism():
    """The derived key is a stable 16 bytes (AES-128)."""
    derived = hbd.password_to_key(SAMPLE_KEY)
    assert len(derived) == 16
    assert derived == hbd.password_to_key(SAMPLE_KEY)
    assert derived != hbd.password_to_key("ZZZZ-EFGH-IJKL-MNOP-QRST-UVWX-YZ01")


def test_password_to_key_known_vector():
    """Guard the derivation (100 rounds of SHA-256, truncated to 16 bytes)."""
    assert hbd.password_to_key(SAMPLE_KEY).hex() == (
        "d3090996feae4f036a84a8a7b4233a6a"
    )


def test_password_to_key_matches_securetar():
    """The local derivation must match securetar's, or passing password= would break.

    This is what makes the securetar >= 2025.12.0 migration safe: the library derives
    the key itself, and it must land on exactly the same bytes as the old key= path.
    """
    key_derivation = getattr(securetar, "KeyDerivationV2", None)
    if key_derivation is None:
        pytest.skip("securetar < 2026.2.0 does not expose KeyDerivationV2")
    assert hbd.password_to_key(SAMPLE_KEY) == key_derivation._password_to_key(SAMPLE_KEY)


def test_securetar_kwargs_matches_installed_signature():
    """The shim must pass whichever argument the installed securetar accepts."""
    params = inspect.signature(securetar.SecureTarFile.__init__).parameters
    kwargs = hbd.securetar_kwargs(SAMPLE_KEY)

    assert len(kwargs) == 1
    argument = next(iter(kwargs))
    assert argument in params, f"securetar does not accept {argument!r}"

    if argument == "password":
        assert kwargs["password"] == SAMPLE_KEY
    else:
        assert kwargs["key"] == hbd.password_to_key(SAMPLE_KEY)


def test_extract_key_from_kit(tmp_path):
    """The key is picked out of a realistic emergency kit file."""
    kit = tmp_path / "home_assistant_backup_emergency_kit.txt"
    kit.write_text(
        "Home Assistant backup emergency kit\n"
        "\n"
        "Encryption key\n"
        f"{SAMPLE_KEY}\n"
        "\n"
        "Keep this file somewhere safe.\n"
    )
    assert hbd.extract_key_from_kit(str(kit)) == SAMPLE_KEY


def test_extract_key_from_kit_without_key(tmp_path):
    """A file with no key yields None rather than a false positive."""
    kit = tmp_path / "notes.txt"
    kit.write_text("There is no encryption key in this file.\nSHORT-WORD-HERE\n")
    assert hbd.extract_key_from_kit(str(kit)) is None


def test_extract_key_from_kit_missing_file(tmp_path):
    """A missing file is reported as no key, not an exception."""
    assert hbd.extract_key_from_kit(str(tmp_path / "absent.txt")) is None


def test_tar_filter_matches_python_support():
    """The filter kwarg is only passed on interpreters that actually accept it."""
    import tarfile

    supported = "filter" in inspect.signature(tarfile.TarFile.extractall).parameters
    assert bool(hbd._TAR_FILTER) is supported
    if supported:
        assert hbd._TAR_FILTER == {"filter": "fully_trusted"}
