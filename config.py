import os
from pathlib import Path
from typing import Optional

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed

class Config:
    """Application configuration class."""
    
    # Server Configuration
    HOST: str = os.getenv('HOST', '0.0.0.0')
    PORT: int = int(os.getenv('PORT', '8000'))
    RELOAD: bool = os.getenv('RELOAD', 'False').lower() == 'true'
    
    # Database Configuration
    DATABASE_URL: str = os.getenv('DATABASE_URL', 'sqlite:///./racing.db')
    
    # API Configuration
    FORMFAV_BASE_URL: str = os.getenv('FORMFAV_BASE_URL', 'https://api.formfav.com')
    FORMFAV_API_KEY: Optional[str] = os.getenv('FORMFAV_API_KEY')
    
    # WebSocket Configuration
    WS_TIMEOUT: int = int(os.getenv('WS_TIMEOUT', '30'))
    
    # Scraping Configuration
    SCRAPE_INTERVAL: int = int(os.getenv('SCRAPE_INTERVAL', '60'))
    MAX_RETRIES: int = int(os.getenv('MAX_RETRIES', '3'))
    
    # Logging Configuration
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
    
    @classmethod
    def validate(cls) -> bool:
        """Validate required configuration values."""
        if not cls.FORMFAV_API_KEY:
            print('Warning: FORMFAV_API_KEY not set')
            return False
        return True

# Create global config instance
config = Config()
