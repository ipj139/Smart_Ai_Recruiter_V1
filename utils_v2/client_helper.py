"""
Helper functions for creating unified LLM clients
Supports any OpenAI-compatible API provider
"""
from openai import OpenAI


def detect_base_url(api_key):
    """Auto-detect base URL from API key pattern
    
    Args:
        api_key: API key string
        
    Returns:
        str: Base URL for the API provider
    """
    if not api_key:
        return "https://api.openai.com/v1"
    
    api_key = str(api_key).strip()
    
    # Groq API keys start with "gsk_"
    if api_key.startswith("gsk_"):
        return "https://api.groq.com/openai/v1"
    
    # OpenRouter API keys start with "sk-or-"
    elif api_key.startswith("sk-or-"):
        return "https://openrouter.ai/api/v1"
    
    # OpenAI API keys start with "sk-"
    elif api_key.startswith("sk-") and not api_key.startswith("sk-or-"):
        return "https://api.openai.com/v1"
    
    # Together AI keys (example pattern)
    elif api_key.startswith("together_"):
        return "https://api.together.xyz/v1"
    
    # Anyscale keys (example pattern)
    elif api_key.startswith("anyscale_"):
        return "https://api.endpoints.anyscale.com/v1"
    
    # Default to OpenAI format (most providers are OpenAI-compatible)
    else:
        return "https://api.openai.com/v1"


def get_llm_client(api_key, base_url=None):
    """Create unified OpenAI-compatible client
    
    Args:
        api_key: API key for the LLM provider
        base_url: Optional base URL. If not provided, auto-detects from API key
        
    Returns:
        OpenAI client instance configured for the provider
    """
    if not api_key:
        raise ValueError("API key is required")
    
    # Auto-detect base_url if not provided
    if not base_url:
        base_url = detect_base_url(api_key)
    
    # Create OpenAI client with provider-specific base_url
    # This works for any OpenAI-compatible API
    client = OpenAI(
        base_url=base_url,
        api_key=api_key
    )
    
    return client

