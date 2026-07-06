import subprocess
import platform
from datetime import datetime, timedelta, timezone

# NOTE: Activation system is disabled in this open-source release.
# Full key management and HWID-based activation logic is preserved below
# for reference — all checks return True to allow free access.

# --- Supabase integration (disabled in open-source release) ---
# from supabase import create_client, Client
# SUPABASE_URL = "URL"
# SUPABASE_KEY = "KEY"
# supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
supabase = None #because main.py file is importing <<supabase>> from here 

def get_raw_hwid():
    system = platform.system()
    try:
        if system == "Windows":
            cmd = 'wmic baseboard get serialnumber'
            output = subprocess.check_output(cmd, shell=True).decode().split('\n')
            return output[1].strip()
        elif system == "Linux":
            with open('/etc/machine-id', 'r') as f:
                return f.read().strip()
        else:
            return "Unsupported System"
    except Exception as e:
        return f"Error: {str(e)}"


def check_expiry_and_update(record):
    """
    Checks whether a key has expired based on its expiry date.
    If expired, updates its status to 'Expired' in the database.
    [Disabled in open-source release]
    """
    status = record.get("status", "").capitalize()

    if status == "Activated" and record.get("expires_at"):
        try:
            expiry_str = record["expires_at"].replace("Z", "+00:00")
            if expiry_str.endswith("+00"):
                expiry_str = expiry_str[:-3] + "+00:00"

            expiry_date = datetime.fromisoformat(expiry_str)
            now = datetime.now(timezone.utc)

            if now > expiry_date:
                # supabase.table("keys_table").update({"status": "Expired"}).eq("id", record["id"]).execute()
                record["status"] = "Expired"

        except Exception as e:
            print(f"⚠️ Error parsing date: {e}")

    return record


def get_account_info(hwid=None):
    """
    Read-only: returns subscription info for the current device.
    Used to display account status in the UI.
    [Disabled in open-source release — returns mock active state]
    """
    hwid = hwid or get_raw_hwid()
    return {
        "found": True,
        "hwid": hwid,
        "code": "OPEN-SOURCE",
        "name": "Free User",
        "status": "Activated",
        "expires_at": None,
        "days_left": 9999,
    }


def verify_and_use_key(input_code):
    """
    Validates a license key, binds it to the device HWID,
    and sets a 30-day expiry on first activation.
    [Disabled in open-source release]
    """
    print("✅ Welcome! (Activation disabled in this release)")
    return True


def checkactivation(hwid):
    """
    Checks whether the current device has an active subscription.
    [Disabled in open-source release]
    """
    print("✅ Free access granted.")
    return True


def main():
    while True:
        print("\n1. [Activate code]")
        print("2. [Exit]")
        print("3. [Check activation]")
        x = input(">>> ").strip()

        if x == "1":
            code = input("Enter your code: ").strip()
            verify_and_use_key(code)
        elif x == "2":
            input("Press [Enter] to exit...")
            break
        elif x == "3":
            uid = get_raw_hwid()
            checkactivation(uid)
        else:
            print("❌ Invalid input, please choose 1, 2 or 3")


if __name__ == "__main__":
    main()
