"""
Configuration for LangGraph Agent System
"""

import os
from typing import Optional
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class AgentConfig:
    """Central configuration for the agent system"""
    
    # Database Configuration
    db_host: str = os.getenv("DB_HOST", "localhost")
    db_port: str = os.getenv("DB_PORT", "5432")
    db_name: str = os.getenv("DB_NAME", "ecom_products")
    db_user: str = os.getenv("DB_USER", "postgres")
    db_password: str = os.getenv("DB_PASSWORD", "")
    
    # Redis Configuration for Session Management
    redis_host: str = os.getenv("REDIS_HOST", "localhost")
    redis_port: int = int(os.getenv("REDIS_PORT", "6379"))
    redis_db: int = int(os.getenv("REDIS_DB", "0"))
    redis_password: Optional[str] = os.getenv("REDIS_PASSWORD")
    
    # OpenAI Configuration
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview")
    openai_embedding_model: str = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    
    # LangSmith Configuration
    langsmith_api_key: Optional[str] = os.getenv("LANGSMITH_API_KEY")
    langsmith_project: str = os.getenv("LANGSMITH_PROJECT", "ecom-product-agent")
    langsmith_tracing: bool = os.getenv("LANGSMITH_TRACING", "true").lower() == "true"
    
    # Agent Configuration
    max_iterations: int = int(os.getenv("AGENT_MAX_ITERATIONS", "10"))
    max_search_results: int = int(os.getenv("MAX_SEARCH_RESULTS", "20"))
    
    # Session Configuration
    session_ttl_seconds: int = int(os.getenv("SESSION_TTL_SECONDS", "3600"))  # 1 hour
    max_conversation_history: int = int(os.getenv("MAX_CONVERSATION_HISTORY", "20"))
    
    # Safety Configuration
    sql_read_only: bool = True  # Always true for safety
    max_sql_results: int = int(os.getenv("MAX_SQL_RESULTS", "100"))
    
    def get_db_url(self) -> str:
        """Get PostgreSQL connection URL"""
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
    
    def get_redis_url(self) -> str:
        """Get Redis connection URL"""
        password_part = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{password_part}{self.redis_host}:{self.redis_port}/{self.redis_db}"
    
    def setup_langsmith(self):
        """Configure LangSmith tracing with detailed logging about destination"""
        # Check configuration options
        verbose_mode = os.getenv("LANGCHAIN_VERBOSE", "false").lower() == "true"
        has_api_key = bool(self.langsmith_api_key)
        tracing_enabled = self.langsmith_tracing
        
        print(f"\n🔍 LangSmith Configuration Check:")
        print(f"   • API Key: {'✅ Present' if has_api_key else '❌ Missing/Commented'}")
        print(f"   • Tracing Enabled: {'✅ Yes' if tracing_enabled else '❌ No'}")
        print(f"   • Verbose Mode: {'✅ Yes' if verbose_mode else '❌ No'}")
        print(f"   • Project: {self.langsmith_project}")
        
        if verbose_mode:
            # Console verbose mode - no cloud tracing
            os.environ["LANGCHAIN_VERBOSE"] = "true"
            os.environ["LANGCHAIN_TRACING_V2"] = "false"
            # Ensure no cloud endpoints
            os.environ.pop("LANGCHAIN_API_KEY", None)
            os.environ.pop("LANGCHAIN_ENDPOINT", None)
            
            print(f"\n🖥️ CONSOLE TRACING ENABLED")
            print(f"   📍 Destination: LOCAL CONSOLE ONLY")
            print(f"   📝 LLM calls, tool executions, and agent decisions will print below")
            print(f"   🚫 NO data sent to LangSmith cloud servers")
            
        elif has_api_key and tracing_enabled:
            # Cloud tracing with API key
            os.environ["LANGCHAIN_TRACING_V2"] = "true"
            os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
            os.environ["LANGCHAIN_API_KEY"] = self.langsmith_api_key
            os.environ["LANGCHAIN_PROJECT"] = self.langsmith_project
            os.environ["LANGCHAIN_CALLBACKS_BACKGROUND"] = "true"
            os.environ["LANGCHAIN_VERBOSE"] = "false"  # Disable console verbose when using cloud
            
            print(f"\n☁️ LANGSMITH CLOUD TRACING ENABLED")
            print(f"   📍 Destination: LangSmith Cloud Servers")
            print(f"   🌐 URL: https://smith.langchain.com/o/{self.langsmith_project}")
            print(f"   📡 All traces will be uploaded to LangSmith dashboard")
            
        else:
            # No tracing
            os.environ["LANGCHAIN_TRACING_V2"] = "false"
            os.environ["LANGCHAIN_VERBOSE"] = "false"
            os.environ.pop("LANGCHAIN_API_KEY", None)
            os.environ.pop("LANGCHAIN_ENDPOINT", None)
            
            print(f"\n❌ TRACING DISABLED")
            print(f"   📍 Destination: NONE")
            print(f"   🚫 No tracing output (neither console nor cloud)")
            if not has_api_key and not verbose_mode:
                print(f"   💡 To enable: Add LANGSMITH_API_KEY for cloud OR LANGCHAIN_VERBOSE=true for console")
        
        print(f"{'='*70}")


# Global config instance
config = AgentConfig()
config.setup_langsmith()