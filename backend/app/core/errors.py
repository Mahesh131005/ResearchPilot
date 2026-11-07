class ProviderError(Exception):
    """Base exception for AI and search provider errors."""
    pass

class ProviderAuthenticationError(ProviderError):
    """Raised when an API key is invalid, missing in live mode, or unauthorized."""
    pass

class ProviderQuotaError(ProviderError):
    """Raised when API rate limits or quota are exhausted."""
    pass

class ProviderAPIError(ProviderError):
    """Raised when an external provider API call fails due to network, timeout, or server error."""
    pass

