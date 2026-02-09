"""
API Views for common app models
"""
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from .models import Banner
from .serializers import BannerSerializer, BannerListSerializer


class BannerViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for banners
    
    list: Get all active banners (public access)
    retrieve: Get a specific banner by ID (public access)
    active: Get active banners filtered by type (custom action)
    """
    
    permission_classes = [AllowAny]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['priority', 'start_date', 'created_at']
    ordering = ['-priority', '-start_date']
    
    def get_queryset(self):
        """
        Get all active banners within valid dates
        Supports filtering by banner_type via query params
        """
        queryset = Banner.get_active_banners()
        
        # Filter by banner_type if provided
        banner_type = self.request.query_params.get('banner_type', None)
        if banner_type:
            queryset = queryset.filter(banner_type=banner_type)
        
        return queryset
    
    def get_serializer_class(self):
        """
        Use lightweight serializer for list, full serializer for detail
        """
        if self.action == 'list':
            return BannerListSerializer
        return BannerSerializer
    
    @action(detail=False, methods=['get'], url_path='active')
    def active_banners(self, request):
        """
        Get active banners, optionally filtered by banner_type
        
        Query params:
        - banner_type: Filter by type (home, course, offer)
        
        Example: GET /api/banners/active/?banner_type=home
        """
        banner_type = request.query_params.get('banner_type', None)
        
        queryset = Banner.get_active_banners(banner_type=banner_type)
        serializer = BannerListSerializer(
            queryset,
            many=True,
            context={'request': request}
        )
        
        return Response({
            'count': queryset.count(),
            'results': serializer.data
        })
    
    @action(detail=False, methods=['get'], url_path='by-type/(?P<type_name>[^/.]+)')
    def by_type(self, request, type_name=None):
        """
        Get active banners by type (home, course, offer)
        
        Example: GET /api/banners/by-type/home/
        """
        valid_types = ['home', 'course', 'offer']
        
        if type_name not in valid_types:
            return Response(
                {'error': f'Invalid banner type. Must be one of: {", ".join(valid_types)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        queryset = Banner.get_active_banners(banner_type=type_name)
        serializer = BannerListSerializer(
            queryset,
            many=True,
            context={'request': request}
        )
        
        return Response({
            'banner_type': type_name,
            'count': queryset.count(),
            'results': serializer.data
        })


# ---------------------------------------------------------------------------
# Static site pages (About / Contact / Policies)
# ---------------------------------------------------------------------------
from django.shortcuts import render, redirect
from django.core.mail import send_mail
from django.conf import settings
from django.contrib import messages
from apps.platformadmin.models import TeamMember


def about_view(request):
    """Render About Us page"""
    team_members = TeamMember.objects.filter(is_active=True).order_by('display_order', 'name')
    return render(request, 'pages/about.html', {'team_members': team_members})


def contact_view(request):
    """Render Contact Us page and handle simple contact form POST"""
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        subject = request.POST.get('subject', 'Website contact').strip()
        message = request.POST.get('message', '').strip()

        if not (name and email and message):
            messages.error(request, 'Please fill in all required fields.')
            return render(request, 'pages/contact.html', {'name': name, 'email': email, 'subject': subject, 'message': message})

        # Send email to site admin / support
        try:
            full_message = f"From: {name} <{email}>\n\n{message}"
            send_mail(
                subject=f"[Contact] {subject}",
                message=full_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[getattr(settings, 'SUPPORT_EMAIL', settings.DEFAULT_FROM_EMAIL)],
                fail_silently=False,
            )
            messages.success(request, 'Your message has been sent. We will contact you shortly.')
            return redirect('contact')
        except Exception:
            messages.error(request, 'Failed to send message. Please try again later or contact support via email.')

    return render(request, 'pages/contact.html')


def privacy_view(request):
    """Render Privacy Policy page"""
    return render(request, 'pages/privacy.html')


def terms_view(request):
    """Render Terms & Conditions page"""
    return render(request, 'pages/terms.html')


def refund_policy_view(request):
    """Render Refund / Cancellation Policy page"""
    return render(request, 'pages/refund_policy.html')
