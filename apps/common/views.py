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
