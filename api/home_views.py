from django.shortcuts import render
from django.db.models import Count, Avg, Q
from django.contrib.auth import get_user_model

from apps.courses.models import Course, Category, Enrollment, Review


def home_view(request):
    """Render the site's homepage template with real course data.

    Supplies `trending_courses`, `categories` and `stats` to the template so
    the home page shows real content instead of dummy/sample cards.
    """
    User = get_user_model()

    # Trending courses: published courses ordered by number of active enrollments
    trending_courses = (
        Course.objects.filter(status='published')
        .annotate(active_students=Count('enrollments', filter=Q(enrollments__status='active')))
        .select_related('teacher', 'category')
        .order_by('-active_students', '-created_at')[:12]
    )

    # Active categories
    categories = Category.objects.filter(is_active=True).order_by('name')[:20]

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
        'categories': categories,
        'stats': stats,
    }

    return render(request, 'home.html', context)
