"""
Caching utilities for LeQ audio learning platform
Optimized for high-traffic shared hosting environments
"""
import hashlib
from functools import wraps
from django.core.cache import cache, caches
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.vary import vary_on_headers
from django.views.decorators.cache import cache_control
import logging

logger = logging.getLogger(__name__)

def generate_cache_key(*args, **kwargs):
    """Generate a consistent cache key from arguments"""
    key_parts = []
    
    # Add positional args
    for arg in args:
        if isinstance(arg, (str, int, float)):
            key_parts.append(str(arg))
        elif hasattr(arg, 'pk'):  # Model instance
            key_parts.append(f"{arg.__class__.__name__}_{arg.pk}")
        else:
            key_parts.append(str(hash(str(arg))))
    
    # Add keyword args
    for k, v in sorted(kwargs.items()):
        if isinstance(v, (str, int, float, bool, type(None))):
            key_parts.append(f"{k}:{v}")
        elif hasattr(v, 'pk'):  # Model instance
            key_parts.append(f"{k}:{v.__class__.__name__}_{v.pk}")
    
    # Create hash for long keys
    key_string = ":".join(key_parts)
    if len(key_string) > 200:  # Django cache key length limit is 250
        key_string = hashlib.md5(key_string.encode()).hexdigest()
    
    return key_string


def cache_view(
    timeout=None,
    cache_alias='default',
    key_prefix=None,
    vary_on=None,
    condition=None,
    per_user=False,
    per_language=False
):
    """
    Advanced view caching decorator with flexible options
    
    Args:
        timeout: Cache timeout in seconds (default: CACHE_TTL['DYNAMIC'])
        cache_alias: Which cache backend to use
        key_prefix: Prefix for cache key
        vary_on: List of GET parameters to include in cache key
        condition: Function that returns True if view should be cached
        per_user: Include user ID in cache key
        per_language: Include language code in cache key
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # Check caching condition
            if condition and not condition(request):
                return view_func(request, *args, **kwargs)
            
            # Build cache key
            key_parts = [key_prefix or view_func.__name__]
            
            # Add URL args and kwargs
            key_parts.extend(str(arg) for arg in args)
            key_parts.extend(f"{k}:{v}" for k, v in kwargs.items())
            
            # Add vary_on parameters
            if vary_on:
                for param in vary_on:
                    value = request.GET.get(param, '')
                    if value:
                        key_parts.append(f"{param}:{value}")
            
            # Add user if per_user
            if per_user and request.user.is_authenticated:
                key_parts.append(f"user:{request.user.id}")
            
            # Add language if per_language
            if per_language:
                from django.utils import translation
                key_parts.append(f"lang:{translation.get_language()}")
            
            cache_key = generate_cache_key(*key_parts)
            cache_timeout = timeout or getattr(settings, 'CACHE_TTL', {}).get('DYNAMIC', 300)
            
            # Get cache backend
            cache_backend = caches[cache_alias]
            
            # Try to get from cache
            cached_response = cache_backend.get(cache_key)
            if cached_response is not None:
                logger.debug(f"Cache HIT for key: {cache_key}")
                return cached_response
            
            # Generate response
            logger.debug(f"Cache MISS for key: {cache_key}")
            response = view_func(request, *args, **kwargs)
            
            # Cache the response if it's successful
            if response.status_code == 200:
                # Render the response if it hasn't been rendered yet
                if hasattr(response, 'render') and not getattr(response, 'is_rendered', True):
                    response.render()
                
                cache_backend.set(cache_key, response, cache_timeout)
                logger.debug(f"Cached response for key: {cache_key} (timeout: {cache_timeout}s)")
            
            return response
        
        return _wrapped_view
    return decorator


def cache_query_result(key, queryset_func, timeout=None, cache_alias='default'):
    """Cache the result of an expensive database query"""
    cache_backend = caches[cache_alias]
    cache_timeout = timeout or getattr(settings, 'CACHE_TTL', {}).get('DYNAMIC', 300)
    
    cached_result = cache_backend.get(key)
    if cached_result is not None:
        logger.debug(f"Query cache HIT for key: {key}")
        return cached_result
    
    logger.debug(f"Query cache MISS for key: {key}")
    result = queryset_func()
    
    # Convert queryset to list to make it serializable
    if hasattr(result, 'all'):
        result = list(result)
    
    cache_backend.set(key, result, cache_timeout)
    logger.debug(f"Cached query result for key: {key} (timeout: {cache_timeout}s)")
    
    return result


def invalidate_cache_pattern(pattern, cache_alias='default'):
    """Invalidate all cache keys matching a pattern"""
    cache_backend = caches[cache_alias]
    
    # For database cache, we need to manually track and invalidate keys
    # This is a simplified version - in production, consider using cache versioning
    try:
        if hasattr(cache_backend, 'delete_many'):
            # This would require custom cache backend implementation
            pass
        else:
            # For now, log the invalidation request
            logger.info(f"Cache invalidation requested for pattern: {pattern}")
    except Exception as e:
        logger.error(f"Cache invalidation failed for pattern {pattern}: {e}")


def warm_cache_key(key, func, timeout=None, cache_alias='default'):
    """Pre-populate cache with a specific key"""
    cache_backend = caches[cache_alias]
    cache_timeout = timeout or getattr(settings, 'CACHE_TTL', {}).get('DYNAMIC', 300)
    
    try:
        result = func()
        cache_backend.set(key, result, cache_timeout)
        logger.info(f"Warmed cache for key: {key}")
        return True
    except Exception as e:
        logger.error(f"Cache warming failed for key {key}: {e}")
        return False


# Predefined cache decorators for common use cases
def cache_homepage(timeout=None):
    """Cache homepage view with smart invalidation"""
    return cache_view(
        timeout=timeout or getattr(settings, 'CACHE_TTL', {}).get('SEMI_STATIC', 7200),
        key_prefix='home',
        vary_on=['page'],
        condition=lambda request: not request.user.is_authenticated or not hasattr(request.user, 'is_staff') or not request.user.is_staff
    )

def cache_course_list(timeout=None):
    """Cache course list with pagination and filters"""
    return cache_view(
        timeout=timeout or getattr(settings, 'CACHE_TTL', {}).get('SEMI_STATIC', 7200),
        key_prefix='course_list',
        vary_on=['page', 'category', 'search', 'level', 'price', 'sort'],
        condition=lambda request: request.method == 'GET'
    )

def cache_course_detail(timeout=None):
    """Cache course detail with user-specific data"""
    return cache_view(
        timeout=timeout or getattr(settings, 'CACHE_TTL', {}).get('STATIC', 86400),
        key_prefix='course_detail',
        per_user=True,  # Different cache for enrolled vs non-enrolled users
        condition=lambda request: request.method == 'GET'
    )

def cache_api_response(timeout=None):
    """Cache API responses with appropriate headers"""
    return cache_view(
        timeout=timeout or getattr(settings, 'CACHE_TTL', {}).get('FREQUENT', 300),
        cache_alias='locmem',  # Use faster local memory cache for API
        vary_on=['format'],
        condition=lambda request: request.method == 'GET'
    )


# Cache utilities for template fragments
class FragmentCacheHelper:
    """Helper for managing template fragment caching"""
    
    @staticmethod
    def get_fragment_key(fragment_name, *args, **kwargs):
        """Generate cache key for template fragment"""
        return generate_cache_key(f"fragment:{fragment_name}", *args, **kwargs)
    
    @staticmethod
    def invalidate_fragment(fragment_name, *args, **kwargs):
        """Invalidate a specific template fragment"""
        key = FragmentCacheHelper.get_fragment_key(fragment_name, *args, **kwargs)
        cache.delete(key)
        logger.debug(f"Invalidated fragment cache: {key}")
    
    @staticmethod
    def warm_fragment(fragment_name, template_func, *args, **kwargs):
        """Pre-warm a template fragment"""
        key = FragmentCacheHelper.get_fragment_key(fragment_name, *args, **kwargs)
        return warm_cache_key(key, template_func)


# Cache warming functions for common data
def warm_homepage_data():
    """Pre-warm cache for homepage data"""
    from apps.courses.models import Course, Category
    from django.contrib.auth import get_user_model
    
    User = get_user_model()
    
    # Warm trending courses
    warm_cache_key(
        f"{settings.CACHE_KEYS['HOME_TRENDING']}:all",
        lambda: list(Course.objects.filter(status='published')
                    .select_related('teacher', 'category')
                    .order_by('-created_at')[:12])
    )
    
    # Warm featured courses
    warm_cache_key(
        f"{settings.CACHE_KEYS['HOME_FEATURED']}:all",
        lambda: list(Course.objects.filter(status='published', is_featured=True)
                    .select_related('teacher', 'category')
                    .order_by('-created_at')[:12])
    )
    
    # Warm categories
    warm_cache_key(
        f"{settings.CACHE_KEYS['CATEGORY_LIST']}:active",
        lambda: list(Category.objects.filter(is_active=True)
                    .order_by('display_order', 'name')[:20])
    )
    
    logger.info("Homepage data cache warmed successfully")


def warm_course_data():
    """Pre-warm cache for course-related data"""
    from apps.courses.models import Course, Category
    
    # Warm popular courses
    warm_cache_key(
        f"{settings.CACHE_KEYS['COURSE_LIST']}:popular",
        lambda: list(Course.objects.filter(status='published')
                    .select_related('teacher', 'category')
                    .order_by('-created_at')[:20])
    )
    
    logger.info("Course data cache warmed successfully")