import os
import ssl
import subprocess
import sys

def install_certificates():
    print("Installing/Upgrading certifi...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "certifi"])
    
    import certifi
    
    openssl_dir, openssl_cafile = os.path.split(ssl.get_default_verify_paths().openssl_cafile)
    print(f"Target CA file: {openssl_cafile}")
    
    relpath_to_certifi_cafile = os.path.relpath(certifi.where(), openssl_dir)
    print("Removing any existing file or link...")
    try:
        os.remove(openssl_cafile)
    except FileNotFoundError:
        pass
    except PermissionError:
        print(f"Permission error removing {openssl_cafile}. Try running with sudo.")
        return

    print("Creating symlink to certifi certificate bundle...")
    try:
        os.chdir(openssl_dir)
        os.symlink(relpath_to_certifi_cafile, openssl_cafile)
        print("Update complete. SSL certificates installed successfully!")
    except Exception as e:
        print(f"Error creating symlink: {e}")
        print("If you see a permission error, you might need to run this script with sudo.")

if __name__ == '__main__':
    install_certificates()
