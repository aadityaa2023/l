from django.shortcuts import render
from django.db.models import Count, Avg, Q, Prefetch
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.conf import settings
from django.views.decorators.cache import cache_control

from apps.courses.models import Course, Category, Enrollment, Review
from apps.common.cache_utils import cache_homepage, cache_query_result
from apps.common.query_optimization import (
    get_optimized_course_queryset,
    get_optimized_categories_with_courses,
    get_cached_platform_stats
)


@cache_control(public=True, max_age=300)  # Browser cache for 5 minutes
@cache_homepage(timeout=settings.CACHE_TTL['SEMI_STATIC'])  # Database cache for 2 hours
def home_view(request):
    """Render the site's homepage template with category-wise course grouping.

    Supplies category-grouped courses, trending courses, and stats to enable
    KukuFM-style horizontal scrolling UI pattern.
    
    Heavily cached and optimized for performance on shared hosting.
    """
    User = get_user_model()

    # Trending courses with optimized queries and caching
    trending_courses = cache_query_result(
        f"{settings.CACHE_KEYS['HOME_TRENDING']}:all",
        lambda: list(get_optimized_course_queryset(
            order_by='popular',
            limit=12
        )),
        timeout=settings.CACHE_TTL['FREQUENT']
    )

    # Featured courses with optimized queries and caching
    featured_courses = cache_query_result(
        f"{settings.CACHE_KEYS['HOME_FEATURED']}:all",
        lambda: list(get_optimized_course_queryset(
            filters={'featured': True},
            order_by='-created_at',
            limit=12
        )),
        timeout=settings.CACHE_TTL['SEMI_STATIC']
    )

    # Category-wise courses with optimized prefetching
    categories_with_courses = cache_query_result(
        f"{settings.CACHE_KEYS['CATEGORY_LIST']}:with_courses",
        lambda: get_optimized_categories_with_courses(max_courses_per_category=15),
        timeout=settings.CACHE_TTL['SEMI_STATIC']
    )

    # All active categories for category filter pills
    all_categories = cache_query_result(
        f"{settings.CACHE_KEYS['CATEGORY_LIST']}:active",
        lambda: list(Category.objects.filter(is_active=True)
                    .only('id', 'name', 'slug', 'display_order')
                    .order_by('display_order', 'name')[:20]),
        timeout=settings.CACHE_TTL['STATIC']
    )

    # Platform stats with optimized queries and caching
    stats = get_cached_platform_stats()

    context = {
        'trending_courses': trending_courses,
        'featured_courses': featured_courses,
        'categories_with_courses': categories_with_courses,
        'categories': all_categories,
        'stats': stats,
    }

    return render(request, 'home.html', context)
