from supabase import create_client, Client
from app.core.config import settings

# Initialize the Supabase client
# settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY 
# come from the config.py file we created earlier.
supabase: Client = create_client(
    settings.SUPABASE_URL, 
    settings.SUPABASE_SERVICE_ROLE_KEY
)

def get_supabase():
    """
    Helper function to return the supabase client.
    Can be used for Dependency Injection in FastAPI routes.
    """
    return supabase