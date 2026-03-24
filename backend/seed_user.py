import os
from supabase import create_client
from config import settings

supabase = create_client(settings.supabase_url, settings.supabase_service_role_key)

def fix_doctor_password():
    print("Finding doctor user...")
    users_resp = supabase.auth.admin.list_users()
    # supabase-py v2 returns a list directly
    doc_user = next((u for u in users_resp if getattr(u, 'email', None) == "doctor@test.vitalnet"), None)
    
    if doc_user:
        print(f"Found doctor user: {doc_user.id}. Updating password and metadata...")
        supabase.auth.admin.update_user_by_id(doc_user.id, {
            "password": "TestDoctor2026!",
            "app_metadata": {"role": "doctor"}
        })
        print("Doctor user updated successfully.")
    else:
        print("Doctor user not found. Creating...")
        supabase.auth.admin.create_user({
            "email": "doctor@test.vitalnet",
            "password": "TestDoctor2026!",
            "email_confirm": True,
            "app_metadata": {"role": "doctor"}
        })
        print("Doctor user created.")

if __name__ == "__main__":
    fix_doctor_password()
