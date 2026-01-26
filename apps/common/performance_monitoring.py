"""
Performance monitoring utilities for LeQ caching system
"""
import time
import logging
from functools import wraps
from django.core.cache import cache
from django.conf import settings
from django.db import connection
from django.utils import timezone

logger = logging.getLogger(__name__)


class CachePerformanceMonitor:
    """Monitor cache performance and database query efficiency"""
    
    def __init__(self):
        self.cache_hits = 0
        self.cache_misses = 0
        self.query_count = 0
        self.total_time = 0
    
    def record_cache_hit(self, key, time_taken=0):
        """Record a cache hit"""
        self.cache_hits += 1
        self.total_time += time_taken
        logger.debug(f"Cache HIT: {key} ({time_taken:.4f}s)")
    
    def record_cache_miss(self, key, time_taken=0):
        """Record a cache miss"""
        self.cache_misses += 1
        self.total_time += time_taken
        logger.debug(f"Cache MISS: {key} ({time_taken:.4f}s)")
    
    def record_query(self, query_time):
        """Record database query execution"""
        self.query_count += 1
        logger.debug(f"DB Query executed ({query_time:.4f}s)")
    
    def get_stats(self):
        """Get performance statistics"""
        total_requests = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total_requests * 100) if total_requests > 0 else 0
        avg_time = (self.total_time / total_requests) if total_requests > 0 else 0
        
        return {
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'hit_rate': hit_rate,
            'query_count': self.query_count,
            'avg_response_time': avg_time,
            'total_time': self.total_time
        }
    
    def reset(self):
        """Reset monitoring counters"""
        self.cache_hits = 0
        self.cache_misses = 0
        self.query_count = 0
        self.total_time = 0


# Global performance monitor instance
performance_monitor = CachePerformanceMonitor()


def monitor_cache_performance(func):
    """Decorator to monitor cache performance"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        initial_queries = len(connection.queries)
        
        try:
            result = func(*args, **kwargs)
            end_time = time.time()
            execution_time = end_time - start_time
            
            # Count database queries
            query_count = len(connection.queries) - initial_queries
            for _ in range(query_count):
                performance_monitor.record_query(execution_time / query_count if query_count > 0 else 0)
            
            logger.info(f"Function {func.__name__} executed in {execution_time:.4f}s with {query_count} queries")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {str(e)}")
            raise
        
    return wrapper


def log_cache_usage():
    """Log current cache usage statistics"""
    try:
        stats = performance_monitor.get_stats()
        logger.info(f"Cache Performance: {stats['hit_rate']:.1f}% hit rate, "
                   f"{stats['cache_hits']} hits, {stats['cache_misses']} misses, "
                   f"{stats['query_count']} queries")
        
        # Database cache specific stats
        if 'default' in settings.CACHES:
            with connection.cursor() as cursor:
                cache_table = settings.CACHES['default']['LOCATION']
                cursor.execute(f"SELECT COUNT(*) FROM {cache_table}")
                total_entries = cursor.fetchone()[0]
                
                cursor.execute(f"""
                    SELECT COUNT(*) FROM {cache_table} 
                    WHERE expires > %s
                """, [timezone.now()])
                active_entries = cursor.fetchone()[0]
                
                logger.info(f"Database Cache: {active_entries}/{total_entries} active entries")
                
    except Exception as e:
        logger.error(f"Failed to log cache usage: {str(e)}")


def benchmark_cache_operation(operation_name, operation_func, *args, **kwargs):
    """Benchmark a specific cache operation"""
    start_time = time.time()
    initial_queries = len(connection.queries)
    
    try:
        result = operation_func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time
        query_count = len(connection.queries) - initial_queries
        
        logger.info(f"Benchmark {operation_name}: {execution_time:.4f}s, {query_count} queries")
        
        return {
            'operation': operation_name,
            'execution_time': execution_time,
            'query_count': query_count,
            'result': result
        }
        
    except Exception as e:
        logger.error(f"Benchmark {operation_name} failed: {str(e)}")
        return {
            'operation': operation_name,
            'error': str(e)
        }


class CacheHealthCheck:
    """Health check utilities for cache system"""
    
    @staticmethod
    def check_cache_connectivity():
        """Test if cache backends are accessible"""
        results = {}
        
        for alias, config in settings.CACHES.items():
            try:
                cache_backend = cache.caches[alias]
                test_key = f'health_check_{alias}_{int(time.time())}'
                test_value = 'test_data'
                
                # Test set operation
                cache_backend.set(test_key, test_value, 60)
                
                # Test get operation
                retrieved = cache_backend.get(test_key)
                
                if retrieved == test_value:
                    results[alias] = {'status': 'healthy', 'message': 'Cache working correctly'}
                else:
                    results[alias] = {'status': 'error', 'message': 'Data retrieval mismatch'}
                
                # Cleanup test key
                cache_backend.delete(test_key)
                
            except Exception as e:
                results[alias] = {'status': 'error', 'message': str(e)}
        
        return results
    
    @staticmethod
    def check_database_cache_table():
        """Check if database cache table exists and is accessible"""
        try:
            if 'default' in settings.CACHES and settings.CACHES['default']['BACKEND'].endswith('DatabaseCache'):
                cache_table = settings.CACHES['default']['LOCATION']
                
                with connection.cursor() as cursor:
                    # Check if table exists
                    cursor.execute(f"SELECT COUNT(*) FROM {cache_table}")
                    total_entries = cursor.fetchone()[0]
                    
                    return {
                        'status': 'healthy',
                        'message': f'Database cache table accessible with {total_entries} entries'
                    }
            else:
                return {'status': 'skipped', 'message': 'Database cache not configured'}
                
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    @staticmethod
    def check_cache_performance():
        """Check cache performance metrics"""
        stats = performance_monitor.get_stats()
        
        performance_status = 'healthy'
        messages = []
        
        # Check hit rate
        if stats['hit_rate'] < 70:
            performance_status = 'warning'
            messages.append(f"Low cache hit rate: {stats['hit_rate']:.1f}%")
        
        # Check average response time
        if stats['avg_response_time'] > 1.0:
            performance_status = 'warning'
            messages.append(f"High average response time: {stats['avg_response_time']:.3f}s")
        
        # Check query count
        if stats['query_count'] > 50:
            performance_status = 'warning'
            messages.append(f"High database query count: {stats['query_count']}")
        
        return {
            'status': performance_status,
            'message': '; '.join(messages) if messages else 'Performance metrics look good',
            'stats': stats
        }


def generate_performance_report():
    """Generate a comprehensive performance report"""
    report = {
        'timestamp': timezone.now().isoformat(),
        'cache_connectivity': CacheHealthCheck.check_cache_connectivity(),
        'database_cache': CacheHealthCheck.check_database_cache_table(),
        'performance_metrics': CacheHealthCheck.check_cache_performance(),
    }
    
    # Log the report
    logger.info(f"Performance Report Generated: {report}")
    
    return report


# Middleware to track request performance
class CachePerformanceMiddleware:
    """Middleware to track cache performance per request"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Reset counters for new request
        initial_queries = len(connection.queries)
        start_time = time.time()
        
        response = self.get_response(request)
        
        # Calculate metrics
        end_time = time.time()
        execution_time = end_time - start_time
        query_count = len(connection.queries) - initial_queries
        
        # Add performance headers for debugging
        if settings.DEBUG:
            response['X-Cache-Queries'] = str(query_count)
            response['X-Cache-Time'] = f"{execution_time:.4f}"
        
        # Log performance for slow requests
        if execution_time > 2.0 or query_count > 10:
            logger.warning(f"Slow request: {request.path} took {execution_time:.4f}s with {query_count} queries")
        
        return response