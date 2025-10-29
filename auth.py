import os
import json
import pyotp
import hashlib
import datetime
from dotenv import load_dotenv
from angel_api import AngelOneAPI

# Load environment variables
load_dotenv()

class AuthManager:
    def __init__(self, credentials_file="credentials.json"):
        """
        Initialize the authentication manager
        
        Args:
            credentials_file (str): Path to the credentials file
        """
        self.credentials_file = credentials_file
        self.current_user = None
        self.api = None
        
        # Create credentials file if it doesn't exist
        if not os.path.exists(credentials_file):
            with open(credentials_file, 'w') as f:
                json.dump({}, f)
    
    def register_user(self, username, password, api_key, client_id, client_password, totp_key=None):
        """
        Register a new user with Angel One credentials
        
        Args:
            username (str): Username for the application
            password (str): Password for the application
            api_key (str): Angel One API key
            client_id (str): Angel One client ID
            client_password (str): Angel One password
            totp_key (str, optional): TOTP key for 2FA
            
        Returns:
            bool: True if registration successful, False otherwise
        """
        try:
            # Hash the password
            hashed_password = self._hash_password(password)
            
            # Load existing credentials
            with open(self.credentials_file, 'r') as f:
                credentials = json.load(f)
            
            # Check if username already exists
            if username in credentials:
                return False, "Username already exists"
            
            # Add new user
            credentials[username] = {
                "password": hashed_password,
                "api_key": api_key,
                "client_id": client_id,
                "client_password": client_password,
                "totp_key": totp_key,
                "created_at": datetime.datetime.now().isoformat()
            }
            
            # Save credentials
            with open(self.credentials_file, 'w') as f:
                json.dump(credentials, f, indent=4)
            
            return True, "Registration successful"
        
        except Exception as e:
            return False, f"Registration failed: {str(e)}"
    
    def login(self, username, password, totp_code=None):
        """
        Login with username and password
        
        Args:
            username (str): Username
            password (str): Password
            totp_code (str, optional): TOTP code for 2FA
            
        Returns:
            tuple: (success, message)
        """
        try:
            # Load credentials
            with open(self.credentials_file, 'r') as f:
                credentials = json.load(f)
            
            # Check if username exists
            if username not in credentials:
                return False, "Invalid username or password"
            
            # Check password
            hashed_password = self._hash_password(password)
            if credentials[username]["password"] != hashed_password:
                return False, "Invalid username or password"
            
            # Check TOTP if enabled
            if credentials[username].get("totp_key"):
                if not totp_code:
                    return False, "TOTP code required"
                
                totp = pyotp.TOTP(credentials[username]["totp_key"])
                if not totp.verify(totp_code):
                    return False, "Invalid TOTP code"
            
            # Set current user
            self.current_user = username
            
            # Initialize API
            self.api = AngelOneAPI()
            login_result = self.api.connect(
                api_key=credentials[username]["api_key"],
                client_id=credentials[username]["client_id"],
                password=credentials[username]["client_password"],
                totp_key=credentials[username].get("totp_key")
            )
            
            if not login_result:
                return False, "Failed to connect to Angel One API"
            
            return True, "Login successful"
        
        except Exception as e:
            return False, f"Login failed: {str(e)}"
    
    def logout(self):
        """
        Logout current user
        
        Returns:
            bool: True if logout successful
        """
        if self.api:
            self.api.disconnect()
        
        self.current_user = None
        self.api = None
        return True
    
    def get_api(self):
        """
        Get the API instance for the current user
        
        Returns:
            AngelOneAPI: API instance
        """
        return self.api
    
    def is_logged_in(self):
        """
        Check if a user is logged in
        
        Returns:
            bool: True if logged in
        """
        return self.current_user is not None and self.api is not None
    
    def get_current_user(self):
        """
        Get current user
        
        Returns:
            str: Username
        """
        return self.current_user
    
    def update_credentials(self, username, field, value):
        """
        Update user credentials
        
        Args:
            username (str): Username
            field (str): Field to update
            value: New value
            
        Returns:
            bool: True if update successful
        """
        try:
            # Load credentials
            with open(self.credentials_file, 'r') as f:
                credentials = json.load(f)
            
            # Check if username exists
            if username not in credentials:
                return False
            
            # Update field
            if field == "password":
                value = self._hash_password(value)
            
            credentials[username][field] = value
            
            # Save credentials
            with open(self.credentials_file, 'w') as f:
                json.dump(credentials, f, indent=4)
            
            return True
        
        except Exception:
            return False
    
    def enable_2fa(self, username, password):
        """
        Enable 2FA for a user
        
        Args:
            username (str): Username
            password (str): Password
            
        Returns:
            tuple: (success, totp_key or error message)
        """
        try:
            # Load credentials
            with open(self.credentials_file, 'r') as f:
                credentials = json.load(f)
            
            # Check if username exists
            if username not in credentials:
                return False, "Invalid username"
            
            # Check password
            hashed_password = self._hash_password(password)
            if credentials[username]["password"] != hashed_password:
                return False, "Invalid password"
            
            # Generate TOTP key
            totp_key = pyotp.random_base32()
            
            # Update credentials
            credentials[username]["totp_key"] = totp_key
            
            # Save credentials
            with open(self.credentials_file, 'w') as f:
                json.dump(credentials, f, indent=4)
            
            return True, totp_key
        
        except Exception as e:
            return False, f"Failed to enable 2FA: {str(e)}"
    
    def disable_2fa(self, username, password, totp_code):
        """
        Disable 2FA for a user
        
        Args:
            username (str): Username
            password (str): Password
            totp_code (str): TOTP code
            
        Returns:
            tuple: (success, message)
        """
        try:
            # Load credentials
            with open(self.credentials_file, 'r') as f:
                credentials = json.load(f)
            
            # Check if username exists
            if username not in credentials:
                return False, "Invalid username"
            
            # Check password
            hashed_password = self._hash_password(password)
            if credentials[username]["password"] != hashed_password:
                return False, "Invalid password"
            
            # Check if 2FA is enabled
            if not credentials[username].get("totp_key"):
                return False, "2FA is not enabled"
            
            # Verify TOTP code
            totp = pyotp.TOTP(credentials[username]["totp_key"])
            if not totp.verify(totp_code):
                return False, "Invalid TOTP code"
            
            # Remove TOTP key
            credentials[username].pop("totp_key")
            
            # Save credentials
            with open(self.credentials_file, 'w') as f:
                json.dump(credentials, f, indent=4)
            
            return True, "2FA disabled successfully"
        
        except Exception as e:
            return False, f"Failed to disable 2FA: {str(e)}"
    
    def _hash_password(self, password):
        """
        Hash password using SHA-256
        
        Args:
            password (str): Password
            
        Returns:
            str: Hashed password
        """
        return hashlib.sha256(password.encode()).hexdigest()