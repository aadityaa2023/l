"""
Utility functions for YouTube video URL validation and processing.
"""
import re
from typing import Optional, Tuple


def extract_youtube_video_id(url: str) -> Optional[str]:
    """
    Extract YouTube video ID from various YouTube URL formats.
    
    Supports:
    - https://www.youtube.com/watch?v=VIDEO_ID
    - https://youtu.be/VIDEO_ID
    - https://www.youtube.com/embed/VIDEO_ID
    - https://m.youtube.com/watch?v=VIDEO_ID
    - https://youtube.com/watch?v=VIDEO_ID (with or without www)
    
    Args:
        url: YouTube URL string
        
    Returns:
        Video ID if valid YouTube URL, None otherwise
    """
    if not url:
        return None
    
    # Pattern for various YouTube URL formats
    patterns = [
        r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/watch\?v=([a-zA-Z0-9_-]{11})',  # Standard watch URL
        r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/embed\/([a-zA-Z0-9_-]{11})',     # Embed URL
        r'(?:https?:\/\/)?youtu\.be\/([a-zA-Z0-9_-]{11})',                         # Shortened URL
        r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/v\/([a-zA-Z0-9_-]{11})',         # Old embed URL
        r'(?:https?:\/\/)?m\.youtube\.com\/watch\?v=([a-zA-Z0-9_-]{11})',          # Mobile URL
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None


def validate_youtube_url(url: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validate a YouTube URL and extract video ID.
    
    Args:
        url: YouTube URL string
        
    Returns:
        Tuple of (is_valid, video_id, error_message)
    """
    if not url or not url.strip():
        return False, None, "YouTube URL is required."
    
    url = url.strip()
    
    # Extract video ID
    video_id = extract_youtube_video_id(url)
    
    if not video_id:
        return False, None, "Invalid YouTube URL. Please enter a valid YouTube video link."
    
    return True, video_id, None


def get_youtube_embed_url(video_id: str, autoplay: bool = False, 
                          controls: bool = True, modestbranding: bool = True, 
                          use_nocookie: bool = True) -> str:
    """
    Generate YouTube embed URL from video ID with customization options.
    
    Args:
        video_id: YouTube video ID
        autoplay: Whether to autoplay the video (default: False)
        controls: Show video controls (default: True)
        modestbranding: Use modest branding (default: True)
        use_nocookie: Use nocookie domain for better embedding (default: True)
        
    Returns:
        YouTube embed URL
    """
    params = []
    
    # Only add essential parameters to avoid conflicts
    if autoplay:
        params.append('autoplay=1')
    
    if not controls:
        params.append('controls=0')
    
    # Minimal parameters for IFrame API integration
    params.append('rel=0')              # Don't show related videos
    params.append('modestbranding=1')   # Remove YouTube logo
    params.append('showinfo=0')         # Hide video title and uploader info
    params.append('iv_load_policy=3')   # Hide video annotations
    params.append('fs=0')               # Disable YouTube's fullscreen (we'll use custom)
    params.append('cc_load_policy=0')   # Hide closed captions by default
    params.append('controls=0')         # Hide YouTube controls completely
    params.append('enablejsapi=1')      # Enable JavaScript API for custom controls
    
    param_string = '&'.join(params) if params else ''
    
    # Use nocookie domain for better compatibility and privacy
    domain = 'www.youtube-nocookie.com' if use_nocookie else 'www.youtube.com'
    base_url = f'https://{domain}/embed/{video_id}'
    
    if param_string:
        return f'{base_url}?{param_string}'
    
    return base_url


def get_youtube_thumbnail_url(video_id: str, quality: str = 'high') -> str:
    """
    Get YouTube video thumbnail URL.
    
    Args:
        video_id: YouTube video ID
        quality: Thumbnail quality ('default', 'medium', 'high', 'standard', 'maxres')
        
    Returns:
        Thumbnail URL
    """
    quality_map = {
        'default': 'default',      # 120x90
        'medium': 'mqdefault',     # 320x180
        'high': 'hqdefault',       # 480x360
        'standard': 'sddefault',   # 640x480
        'maxres': 'maxresdefault'  # 1280x720
    }
    
    quality_code = quality_map.get(quality, 'hqdefault')
    
    return f'https://img.youtube.com/vi/{video_id}/{quality_code}.jpg'


def is_youtube_url(url: str) -> bool:
    """
    Quick check if a URL is a YouTube URL.
    
    Args:
        url: URL string
        
    Returns:
        True if URL appears to be a YouTube URL, False otherwise
    """
    if not url:
        return False
    
    youtube_domains = ['youtube.com', 'youtu.be', 'm.youtube.com', 'www.youtube.com']
    
    return any(domain in url.lower() for domain in youtube_domains)
