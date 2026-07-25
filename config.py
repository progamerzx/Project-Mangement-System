import os
from dotenv import load_dotenv
load_dotenv()

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

class Config:
    """Application configuration.
    Loads configurations from environment variables and retrieves secrets from Azure Key Vault.
    """
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # Azure Key Vault configuration
    KEY_VAULT_URI = os.environ.get('KEY_VAULT_URI')
    
    # If they only specified the vault name, construct the URI
    KEYVAULT_NAME = os.environ.get('KEYVAULT_NAME')
    if KEYVAULT_NAME and not KEY_VAULT_URI:
        KEY_VAULT_URI = f"https://{KEYVAULT_NAME}.vault.azure.net/"
    
    # DB configuration parameters
    DB_SERVER = None
    DB_NAME = None

    @classmethod
    def parse_connection_string(cls, conn_str):
        """Parses a standard SQL Server connection string into server and database parameters."""
        params = {}
        for item in conn_str.split(';'):
            if '=' in item:
                key, val = item.split('=', 1)
                params[key.strip().lower()] = val.strip()
        
        server_raw = params.get('server', '')
        if server_raw.startswith('tcp:'):
            server_raw = server_raw[4:]
        
        server = server_raw.split(',')[0]
        database = params.get('database')
        return server, database

    @classmethod
    def load_config(cls):
        # 1. Attempt to fetch configurations from Key Vault
        if cls.KEY_VAULT_URI:
            print(f"[Config] Connecting to Azure Key Vault: {cls.KEY_VAULT_URI}")
            try:
                # DefaultAzureCredential supports Managed Identity, Environment Variables, Azure CLI, etc.
                credential = DefaultAzureCredential()
                client = SecretClient(vault_url=cls.KEY_VAULT_URI, credential=credential)
                
                # Option A: Check if the entire connection string is stored as a single secret
                conn_string_secrets = ["db-connection-string", "ConnectionString", "connection-string"]
                connection_string_val = None
                
                for secret_name in conn_string_secrets:
                    try:
                        print(f"[Config] Checking for connection string secret: '{secret_name}'...")
                        secret = client.get_secret(secret_name)
                        connection_string_val = secret.value
                        print(f"[Config] Found connection string secret: '{secret_name}'.")
                        break
                    except Exception:
                        continue # Try next secret name
                
                if connection_string_val:
                    # Parse the connection string
                    s, d = cls.parse_connection_string(connection_string_val)
                    if all([s, d]):
                        cls.DB_SERVER, cls.DB_NAME = s, d
                        print("[Config] Successfully parsed database connection info from connection string secret.")
                    else:
                        print("[Config] WARNING: Connection string was found but could not be parsed successfully.")
                
                # Option B: Fallback to fetching individual parameters (Server, Database)
                if not all([cls.DB_SERVER, cls.DB_NAME]):
                    print("[Config] Connection string secret not found/parsed. Fetching individual secrets (Server, Database)...")
                    try:
                        cls.DB_SERVER = client.get_secret("Server").value
                    except Exception:
                        pass
                    try:
                        cls.DB_NAME = client.get_secret("Database").value
                    except Exception:
                        pass
                    if all([cls.DB_SERVER, cls.DB_NAME]):
                        print("[Config] Database configuration parameters successfully retrieved from Key Vault.")
                    
            except Exception as e:
                print(f"[Config] Error retrieving secrets from Key Vault: {e}")
                print("[Config] Attempting fallback to local environment...")

        # 2. Fallback to individual environment variables
        if not all([cls.DB_SERVER, cls.DB_NAME]):
            cls.DB_SERVER = os.environ.get('DB_SERVER')
            cls.DB_NAME = os.environ.get('DB_DATABASE') or os.environ.get('DB_NAME')

        # 3. Fallback to parsing DB_CONNECTION_STRING environment variable if provided
        if not all([cls.DB_SERVER, cls.DB_NAME]):
            conn_str = os.environ.get('DB_CONNECTION_STRING')
            if conn_str:
                print("[Config] Parsing connection parameters from DB_CONNECTION_STRING environment variable...")
                try:
                    s, d = cls.parse_connection_string(conn_str)
                    if all([s, d]):
                        cls.DB_SERVER, cls.DB_NAME = s, d
                except Exception as e:
                    print(f"[Config] Error parsing DB_CONNECTION_STRING: {e}")

        # Final check
        if all([cls.DB_SERVER, cls.DB_NAME]):
            print(f"[Config] Database configuration successfully resolved (Server: {cls.DB_SERVER}, Database: {cls.DB_NAME}).")
        else:
            print("[Config] WARNING: Missing database connection parameters! Please configure Key Vault URI or set environment variables.")
        
        return cls
