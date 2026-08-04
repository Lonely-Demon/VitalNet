"""
Seed/reset test credentials in Supabase Auth & profiles table.
"""
from supabase import create_client
from app.core.config import settings

supabase = create_client(settings.supabase_url, settings.supabase_service_role_key)

TEST_USERS = [
    {
        "email": "asha@test.vitalnet",
        "password": "TestASHA2026!",
        "role": "asha_worker",
        "full_name": "Test ASHA Worker",
        "facility_id": "af6cd076-0929-4b9b-94f5-d7b7c57264ac"
    },
    {
        "email": "doctor@test.vitalnet",
        "password": "TestDoctor2026!",
        "role": "doctor",
        "full_name": "Test Doctor",
        "facility_id": "af6cd076-0929-4b9b-94f5-d7b7c57264ac"
    },
    {
        "email": "supervisor@test.vitalnet",
        "password": "TestSupervisor2026!",
        "role": "supervisor",
        "full_name": "Test Supervisor",
        "facility_id": "af6cd076-0929-4b9b-94f5-d7b7c57264ac"
    },
    {
        "email": "admin@test.vitalnet",
        "password": "TestAdmin2026!",
        "role": "admin",
        "full_name": "Test Administrator",
        "facility_id": None
    }
]

def seed():
    print("Fetching existing auth users...")
    existing_users = supabase.auth.admin.list_users()
    
    for u_info in TEST_USERS:
        email = u_info["email"]
        password = u_info["password"]
        role = u_info["role"]
        full_name = u_info["full_name"]
        facility_id = u_info["facility_id"]
        
        user_obj = next((u for u in existing_users if getattr(u, 'email', None) == email), None)
        
        if user_obj:
            user_id = user_obj.id
            print(f"Updating user {email} ({user_id})...")
            supabase.auth.admin.update_user_by_id(user_id, {
                "password": password,
                "email_confirm": True,
                "app_metadata": {"role": role},
                "user_metadata": {"role": role, "full_name": full_name, "facility_id": facility_id or ""}
            })
        else:
            print(f"Creating user {email}...")
            res = supabase.auth.admin.create_user({
                "email": email,
                "password": password,
                "email_confirm": True,
                "app_metadata": {"role": role},
                "user_metadata": {"role": role, "full_name": full_name, "facility_id": facility_id or ""}
            })
            user_id = res.user.id
            print(f"Created user {email} with id {user_id}")
            
        # Ensure row in profiles table
        profile_row = {
            "id": user_id,
            "full_name": full_name,
            "role": role,
            "facility_id": facility_id,
            "is_active": True
        }
        print(f"Upserting profile for {email}...")
        supabase.table("profiles").upsert(profile_row).execute()
        print(f"Successfully configured {email}!")

if __name__ == "__main__":
    seed()
