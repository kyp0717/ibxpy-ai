"""
Configuration management using pydantic-settings
"""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    # Application
    app_name: str = "IBXPy Trading Backend"
    app_version: str = "0.1.0"
    debug: bool = Field(default=False, description="Debug mode")
    
    # Server
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    
    # CORS
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        description="Allowed CORS origins"
    )
    
    # WebSocket
    ws_heartbeat_interval: int = Field(default=30, description="WebSocket heartbeat interval in seconds")
    ws_max_connections: int = Field(default=100, description="Maximum WebSocket connections")
    
    # TWS Connection
    tws_host: str = Field(default="127.0.0.1", description="TWS/Gateway host")
    tws_port: int = Field(default=7497, description="TWS paper trading port")
    tws_client_id: int = Field(default=1, description="TWS client ID")
    
    # Redis
    redis_url: str = Field(default="redis://localhost:6379", description="Redis connection URL")
    redis_ttl: int = Field(default=300, description="Default Redis TTL in seconds")
    
    # Performance
    max_latency_ms: int = Field(default=10, description="Maximum acceptable latency in milliseconds")
    batch_update_interval_ms: int = Field(default=50, description="Batch update interval in milliseconds")
    
    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Log format (json or text)")
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    def get_tws_connection_string(self) -> str:
        """Get TWS connection string"""
        return f"{self.tws_host}:{self.tws_port}"
    
    @property
    def is_production(self) -> bool:
        """Check if running in production"""
        return not self.debug
    
    @property
    def is_development(self) -> bool:
        """Check if running in development"""
        return self.debug


# Create settings instance
settings = Settings()