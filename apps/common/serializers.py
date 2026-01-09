"""
Serializers for common app models
"""
from rest_framework import serializers
from .models import Banner


class BannerSerializer(serializers.ModelSerializer):
    """
    Serializer for Banner model
    Provides banner data for frontend display
    """
    
    image_url = serializers.SerializerMethodField()
    banner_type_display = serializers.CharField(source='get_banner_type_display', read_only=True)
    is_currently_active = serializers.SerializerMethodField()
    
    class Meta:
        model = Banner
        fields = [
            'id',
            'title',
            'description',
            'image',
            'image_url',
            'button_text',
            'button_link',
            'banner_type',
            'banner_type_display',
            'priority',
            'is_active',
            'is_currently_active',
            'start_date',
            'end_date',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'created_at',
            'updated_at',
        ]
    
    def get_image_url(self, obj):
        """Get the full URL for the banner image"""
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None
    
    def get_is_currently_active(self, obj):
        """Check if banner is currently active"""
        return obj.is_currently_active()


class BannerListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for banner list views
    """
    
    image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Banner
        fields = [
            'id',
            'title',
            'description',
            'image_url',
            'button_text',
            'button_link',
            'banner_type',
            'priority',
        ]
    
    def get_image_url(self, obj):
        """Get the full URL for the banner image"""
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None
