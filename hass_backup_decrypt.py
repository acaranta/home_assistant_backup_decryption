#!/usr/bin/env python3
"""
Home Assistant Backup Decryption Tool
see the README in https://github.com/acaranta/home_assistant_backup_decryption
"""

import sys, os, glob, shutil, re, hashlib
import inspect
import tarfile
import securetar

import argparse

# securetar >= 2025.12.0 renamed SecureTarFile's "key" argument to "password" and
# derives the AES key internally; 2026.2.0 then dropped "mode" entirely. Detect which
# generation is installed so the tool works with any of them. "mode" defaults to "r"
# in every release, so it is never passed.
_SECURETAR_USES_PASSWORD = (
    "password" in inspect.signature(securetar.SecureTarFile.__init__).parameters
)

# tarfile.extractall()'s "filter" argument (PEP 706) only exists in Python 3.12+ and the
# 3.11.4 / 3.10.12 / 3.9.17 / 3.8.17 security backports. Debian 12 ships 3.11.2 without it.
# tarfile.fully_trusted_filter was added by the same patch, so it is an exact feature test.
_TAR_FILTER = {"filter": "fully_trusted"} if hasattr(tarfile, "fully_trusted_filter") else {}


# Symptoms of a wrong key: InvalidPasswordError from securetar 2026.2.0 onwards,
# SecureTarReadError ("the inner tar is not gzip or tar") on newer releases, and a plain
# tarfile.ReadError ("not a gzip file") on older ones, where gunzip chokes on the garbage
# plaintext before securetar gets to validate anything. getattr keeps this working on
# releases that do not define the securetar-specific errors.
_UNREADABLE_ERRORS = tuple(
    exc
    for exc in (
        getattr(securetar, "InvalidPasswordError", None),
        getattr(securetar, "SecureTarReadError", None),
        tarfile.ReadError,
    )
    if exc is not None
)


def securetar_kwargs(password: str) -> dict:
    """Build the SecureTarFile arguments expected by the installed securetar version.

    securetar >= 2025.12.0 takes the raw password and derives the key itself, using the
    exact same derivation as password_to_key(); older releases take the derived key.
    """
    if _SECURETAR_USES_PASSWORD:
        return {"password": password}
    return {"key": password_to_key(password)}


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Home Assistant Backup Decryption Tool')
    parser.add_argument('-i', '--input', 
                        default='/input',
                        help='Input directory containing backup files (default: /input)')
    parser.add_argument('-o', '--output',
                        default='/output',
                        help='Output directory for decrypted files (default: /output)')
    parser.add_argument('-k', '--key',
                        help='Encryption key (Format XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX)',
                        required=False)
    return parser.parse_args()


def password_to_key(password: str) -> bytes:
    """Generate a AES Key from password.

    Matches the implementation in supervisor.backups.utils.password_to_key.
    """
    key: bytes = password.encode()
    for _ in range(100):
        key = hashlib.sha256(key).digest()
    return key[:16]


def extract_key_from_kit(kit_path):
    """Extract encryption key from emergency kit file."""
    try:
        with open(kit_path, 'r') as f:
            content = f.read()
            # Look for the key pattern: XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX
            match = re.search(r'\b([A-Z0-9]{4}-){6}[A-Z0-9]{4}\b', content)
            if match:
                return match.group(0)
    except Exception as e:
        print(f"Error reading emergency kit file: {e}")
    return None

def extract_tar(filename, outdir="/output"):
    """Extract regular tar file."""
    extract_dir = os.path.join(outdir, filename.split("/")[-1])
    try:
        shutil.rmtree(extract_dir)
    except FileNotFoundError:
        pass
    print(f'📦 Extracting {filename}...')
    with tarfile.open(name=filename, mode="r") as _tar:
        _tar.extractall(
            path=extract_dir,
            members=securetar.secure_path(_tar),
            **_TAR_FILTER,
        )
    return extract_dir

def extract_secure_tar(filename, password, outdir="/output"):
    """Extract encrypted tar file using securetar module."""
    
    extraction_dir = os.path.join(outdir, filename.split('/')[-1]).replace('.tar.gz', '')
    print(f'🔓 Decrypting {filename.split("/")[-1]}... to {extraction_dir}')
    try:
        try:
            shutil.rmtree(extraction_dir)
        except FileNotFoundError:
            pass

        tar_args = securetar_kwargs(password)

        # securetar >= 2026.2.0 can check the key up front, turning a cryptic padding or
        # gzip failure halfway through the archive into a clear message.
        probe = securetar.SecureTarFile(filename, gzip=True, **tar_args)
        if hasattr(probe, "validate_password") and not probe.validate_password():
            print(f"❌ Wrong encryption key for {os.path.basename(filename)}")
            return None

        with securetar.SecureTarFile(filename, gzip=True, **tar_args) as istf:
            istf.extractall(
                path=extraction_dir,
                members=securetar.secure_path(istf),
                **_TAR_FILTER,
            )

    except _UNREADABLE_ERRORS:
        # Older securetar only trips over a bad key once it starts reading the archive,
        # where a corrupt file is indistinguishable from a wrong key.
        print(
            f"❌ Could not decrypt {os.path.basename(filename)}: "
            "wrong encryption key or corrupt backup file"
        )
        return None
    except Exception as e:
        print(f"❌ Error during extraction: {str(e)}")
        return None

    return extraction_dir

def main():
    # for line buffering (kept out of module scope so the module stays importable
    # under test runners that replace sys.stdout with an object lacking reconfigure)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)

    print("\n🏠 Home Assistant Backup Decryption Tool")
    print("=======================================")
    if sys.version_info < (3, 11):
        print("⚠️  Python 3.11+ is recommended: securetar 2025.12.0 and later require it.")
    # get parameters
    args = parse_arguments()
    input_dir = args.input
    output_dir = args.output
    print(f"🔍 Input directory: {input_dir}\n📁 Output directory: {output_dir}")
    print("=======================================")
    #check if input_dir exists
    if not os.path.exists(input_dir):
        print(f"❌ Input directory {input_dir} does not exist.")
        sys.exit(1)
    #check if output_dir exists if not, create it
    if not os.path.exists(output_dir):
        print(f"⚠️  Output directory {output_dir} does not exist. Creating it.")
        os.makedirs(output_dir)
        
    # Look for emergency kit file
    kit_files = glob.glob(f"{input_dir}/*emergency*kit*.txt")
    
    # Try to extract key from the kit file first
    key = None
    if kit_files:
        key = extract_key_from_kit(kit_files[0])
        if key:
            print(f"✅ Found encryption key in {kit_files[0]}")
        else:
            print("⚠️  Could not find encryption key in emergency kit file.")
    else:
        print("⚠️  No emergency kit file found.")
    
    #if key not found in kit file then check for command line argument
    if not key and args.key:
        if re.match(r'^([A-Z0-9]{4}-){6}[A-Z0-9]{4}$', args.key):
            key = args.key
            print("✅ Key passed as parameter found and format verified")
            
    # If key not found, ask for manual entry
    if not key:
        print("\nPlease enter your encryption key manually.")
        print("It should be in the format: XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX")
        while True:
            manual_key = input("Key: ").strip()
            if re.match(r'^([A-Z0-9]{4}-){6}[A-Z0-9]{4}$', manual_key):
                key = manual_key
                print("✅ Key format verified")
                break
            else:
                print("❌ Invalid key format. Please try again.")
    
    print("=======================================")
    # Look for tar files
    tar_files = glob.glob(f"{input_dir}/*.tar")
    if not tar_files:
        print("❌ Error: No .tar files found!")
        print(f"ℹ️  Please place your backup .tar files in the input directory ({input_dir}).")
        sys.exit(1)
    
    print(f"📁 Found {len(tar_files)} backup file(s) to process")
    
    print("=======================================")
    success_count = 0
    for tar_file in tar_files:
        try:
            _dirname = extract_tar(tar_file, output_dir)
            # Look for encrypted tar.gz files in the extracted directory
            secure_tars = glob.glob(f'{_dirname}/*.tar.gz')
            if not secure_tars:
                print(f"ℹ️  No encrypted files found in {tar_file}")
                continue
                
            for secure_tar in secure_tars:
                extracted_dir = extract_secure_tar(secure_tar, key, output_dir)
                if extracted_dir:
                    print(f"✅ Successfully decrypted {secure_tar} to {extracted_dir}")
                    print(f"🗑️  Removing encrypted file {secure_tar}")
                    os.remove(secure_tar)  # Remove the encrypted file after successful extraction
                    success_count += 1
                    
            print(f"🗑️  Removing Temporary extracted data")
            shutil.rmtree(_dirname)  # Remove the temporary extracted data
            
        except Exception as e:
            print(f"❌ Error processing {tar_file}: {str(e)}")
    if success_count > 0:
        print(f"\n✅ Successfully decrypted {success_count} backup file(s)!")
        print(f"You can find the decrypted files in the extracted directories under {output_dir}.")
    else:
        print("\n⚠️  No files were successfully decrypted.")
        print("Please check that your backup files and emergency kit are correct.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
        sys.exit(1)
