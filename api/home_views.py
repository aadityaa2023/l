from django.shortcuts import render
from django.db.models import Count, Avg, Q, Prefetch
from django.contrib.auth import get_user_model

from apps.courses.models import Course, Category, Enrollment, Review


def home_view(request):
    """Render the site's homepage template with category-wise course grouping.

    Supplies category-grouped courses, trending courses, and stats to enable
    KukuFM-style horizontal scrolling UI pattern.
    """
    User = get_user_model()

    # Trending courses: published courses ordered by number of active enrollments
    trending_courses = (
        Course.objects.filter(status='published')
        .annotate(active_students=Count('enrollments', filter=Q(enrollments__status='active')))
        .select_related('teacher', 'category')
        .order_by('-active_students', '-created_at')[:12]
    )

    # Featured courses: manually curated featured courses
    featured_courses = (
        Course.objects.filter(status='published', is_featured=True)
        .select_related('teacher', 'category')
        .order_by('-created_at')[:12]
    )

    # Category-wise courses for horizontal scrolling sections
    # Get active categories with published courses
    categories_with_courses = []
    active_categories = Category.objects.filter(
        is_active=True,
        parent=None  # Only main categories (not subcategories)
    ).prefetch_related(
        Prefetch(
            'courses',
            queryset=Course.objects.filter(status='published')
            .select_related('teacher', 'category')
            .order_by('-created_at')  # Limit applied per-category in Python
        )
    ).order_by('display_order', 'name')

    # Build list of categories that have at least one published course
    for category in active_categories:
        # Use the prefetched queryset, convert to list and apply per-category limit in Python
        prefetched_courses = list(category.courses.all())
        if prefetched_courses:
            categories_with_courses.append({
                'category': category,
                'courses': prefetched_courses[:15]
            })

    # All active categories for category filter pills
    all_categories = Category.objects.filter(is_active=True).order_by('display_order', 'name')[:20]

    # Basic platform stats
    total_students = Enrollment.objects.filter(status='active').values('student').distinct().count()
    total_courses = Course.objects.filter(status='published').count()
    total_instructors = User.objects.filter(role='teacher').count()

    avg_rating = Review.objects.filter(is_approved=True).aggregate(avg=Avg('rating'))['avg'] or 0
    satisfaction_rate = int(round((avg_rating / 5.0) * 100)) if avg_rating else 0

    stats = {
        'total_students': f"{total_students}" if total_students >= 10000 else total_students,
        'total_courses': total_courses,
        'total_instructors': total_instructors,
        'satisfaction_rate': satisfaction_rate,
    }

    context = {
        'trending_courses': trending_courses,
        'featured_courses': featured_courses,
        'categories_with_courses': categories_with_courses,
        'categories': all_categories,
        'stats': stats,
    }

    return render(request, 'home.html', context)
