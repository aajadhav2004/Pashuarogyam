"""
Rate Limiter for Chatbot Service
Handles API rate limiting, quota management, and response caching
"""
import time
import hashlib
import os
import logging
from typing import Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class GeminiRateLimiter:
    """Enhanced Rate limiting for Gemini API with quota management and caching"""
    
    def __init__(self):
        """Initialize rate limiter with configuration from environment"""
        # Load configuration from environment variables
        self.min_interval = float(os.getenv('GEMINI_MIN_INTERVAL', '2.0'))
        self.max_retries = int(os.getenv('GEMINI_MAX_RETRIES', '3'))
        self.base_backoff = float(os.getenv('GEMINI_BASE_BACKOFF', '5.0'))
        self.max_backoff = float(os.getenv('GEMINI_MAX_BACKOFF', '300.0'))
        
        # Cache configuration
        self.enable_cache = os.getenv('GEMINI_ENABLE_CACHE', 'true').lower() == 'true'
        self.cache_ttl = int(os.getenv('GEMINI_CACHE_TTL', '3600'))
        self.max_cache_size = int(os.getenv('GEMINI_MAX_CACHE_SIZE', '100'))
        
        # Rate limiting state
        self.last_call_time = 0
        self.rate_limit_until = 0
        self.consecutive_failures = 0
        self.quota_exceeded = False
        self.quota_reset_time = 0
        self.daily_calls = 0
        self.max_daily_calls = 1500
        self.last_reset_date = time.strftime('%Y-%m-%d')
        
        # Response cache
        self.response_cache = {}
        self.cache_timestamps = {}
        
        logger.info(f"Rate limiter configured: interval={self.min_interval}s, retries={self.max_retries}, cache_ttl={self.cache_ttl}s")
    
    def wait_if_needed(self):
        """Wait if we need to respect rate limits"""
        current_time = time.time()
        current_date = time.strftime('%Y-%m-%d')
        
        # Reset daily counter if it's a new day
        if current_date != self.last_reset_date:
            self.daily_calls = 0
            self.last_reset_date = current_date
            self.quota_exceeded = False
            self.consecutive_failures = 0
            logger.info("Daily quota counter reset for new day")
        
        # Check daily call limit
        if self.daily_calls >= self.max_daily_calls:
            self.quota_exceeded = True
            logger.warning(f"Daily API call limit reached ({self.max_daily_calls})")
            return True
        
        # Check if quota is exceeded and we need to wait
        if self.quota_exceeded and current_time < self.quota_reset_time:
            return True
        elif self.quota_exceeded and current_time >= self.quota_reset_time:
            self.quota_exceeded = False
            self.consecutive_failures = 0
            logger.info("Daily quota reset, attempting to resume API calls")
        
        # Check if we're still in rate limit period
        if current_time < self.rate_limit_until:
            wait_time = self.rate_limit_until - current_time
            logger.info(f"Rate limited. Waiting {wait_time:.1f} seconds...")
            time.sleep(wait_time)
            return True
        
        # Ensure minimum interval between calls
        time_since_last = current_time - self.last_call_time
        if time_since_last < self.min_interval:
            wait_time = self.min_interval - time_since_last
            time.sleep(wait_time)
        
        self.last_call_time = time.time()
        self.daily_calls += 1
        return False
    
    def handle_rate_limit_error(self, error_message=""):
        """Handle 429 rate limit error with quota detection"""
        self.consecutive_failures += 1
        error_lower = error_message.lower()
        
        # Check if this is a quota exceeded error
        if any(keyword in error_lower for keyword in ["quota", "exceeded", "limit", "50", "resource_exhausted"]):
            self.quota_exceeded = True
            next_day = datetime.now() + timedelta(days=1)
            self.quota_reset_time = next_day.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
            logger.warning("Daily quota exceeded. API calls suspended until next day.")
            return 24 * 3600
        
        # Regular rate limiting
        base_wait = min(30, 1.5 ** min(self.consecutive_failures, 5))
        import random
        jitter = random.uniform(0.9, 1.1)
        wait_time = base_wait * jitter
        
        self.rate_limit_until = time.time() + wait_time
        self.min_interval = min(3, self.min_interval * 1.1)
        
        logger.info(f"Rate limit hit. Backing off for {wait_time:.1f} seconds...")
        return wait_time
    
    def reset_on_success(self):
        """Reset failure count on successful call"""
        self.consecutive_failures = 0
        self.min_interval = max(1.0, self.min_interval * 0.9)
    
    def clear_quota_exceeded_state(self):
        """Clear quota exceeded state"""
        self.quota_exceeded = False
        self.consecutive_failures = 0
        self.rate_limit_until = 0
        logger.info("Quota state cleared")
    
    def is_quota_exceeded(self):
        """Check if quota is currently exceeded"""
        current_time = time.time()
        if self.quota_exceeded and current_time >= self.quota_reset_time:
            self.quota_exceeded = False
        return self.quota_exceeded
    
    def _get_cache_key(self, prompt: str, has_image: bool = False) -> str:
        """Generate cache key for request"""
        content = f"{prompt}_{has_image}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def get_cached_response(self, prompt: str, has_image: bool = False) -> Optional[str]:
        """Get cached response if available and not expired"""
        if not self.enable_cache:
            return None
        
        cache_key = self._get_cache_key(prompt, has_image)
        
        if cache_key in self.response_cache:
            timestamp = self.cache_timestamps.get(cache_key, 0)
            if time.time() - timestamp < self.cache_ttl:
                logger.info("Cache hit for prompt")
                return self.response_cache[cache_key]
            else:
                # Remove expired cache entry
                del self.response_cache[cache_key]
                del self.cache_timestamps[cache_key]
        
        return None
    
    def cache_response(self, prompt: str, response: str, has_image: bool = False):
        """Cache successful response"""
        if not self.enable_cache:
            return
        
        # Check cache size
        if len(self.response_cache) >= self.max_cache_size:
            # Remove oldest entry
            oldest_key = min(self.cache_timestamps, key=self.cache_timestamps.get)
            del self.response_cache[oldest_key]
            del self.cache_timestamps[oldest_key]
        
        cache_key = self._get_cache_key(prompt, has_image)
        self.response_cache[cache_key] = response
        self.cache_timestamps[cache_key] = time.time()
        
        logger.info(f"Response cached. Cache size: {len(self.response_cache)}")
