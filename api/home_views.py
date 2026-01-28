from django.shortcuts import render
from django.db.models import Count, Avg, Q, Prefetch
from django.contrib.auth import get_user_model

from apps.courses.models import Course, Category, Enrollment, Review
from apps.common.query_optimization import (
    get_optimized_course_queryset,
    get_optimized_categories_with_courses,
    get_platform_stats
)


def home_view(request):
    """Render the site's homepage template with category-wise course grouping.

    Supplies category-grouped courses, trending courses, and stats to enable
    KukuFM-style horizontal scrolling UI pattern.
    
    Heavily cached and optimized for performance on shared hosting.
    """
    User = get_user_model()

    # Trending courses
    trending_courses = list(get_optimized_course_queryset(
        order_by='popular',
        limit=12
    ))

    # Featured courses
    featured_courses = list(get_optimized_course_queryset(
        filters={'featured': True},
        order_by='-created_at',
        limit=12
    ))

    # Category-wise courses
    categories_with_courses = get_optimized_categories_with_courses(max_courses_per_category=15)

    # All active categories for category filter pills
    all_categories = list(Category.objects.filter(is_active=True)
                    .only('id', 'name', 'slug', 'display_order')
                    .order_by('display_order', 'name')[:20])

    # Platform stats with optimized queries and caching
    stats = get_platform_stats()

    context = {
        'trending_courses': trending_courses,
        'featured_courses': featured_courses,
        'categories_with_courses': categories_with_courses,
        'categories': all_categories,
        'stats': stats,
    }

    return render(request, 'home.html', context)
