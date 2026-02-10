"""
Test YouTube video URL functionality
"""
from apps.common.youtube_utils import (
    extract_youtube_video_id,
    validate_youtube_url,
    get_youtube_embed_url,
    get_youtube_thumbnail_url,
    is_youtube_url
)


def test_youtube_url_validation():
    """Test YouTube URL validation and video ID extraction"""
    
    print("=" * 60)
    print("Testing YouTube URL Validation")
    print("=" * 60)
    
    # Test cases: (url, expected_video_id, description)
    test_cases = [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ", "Standard watch URL"),
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ", "Shortened URL"),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ", "Embed URL"),
        ("https://m.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ", "Mobile URL"),
        ("https://youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ", "URL without www"),
        ("https://www.youtube.com/v/dQw4w9WgXcQ", "dQw4w9WgXcQ", "Old embed format"),
        ("https://invalid-url.com/video", None, "Invalid URL"),
        ("https://www.youtube.com/playlist?list=XXXXX", None, "Playlist URL (not supported)"),
        ("", None, "Empty URL"),
    ]
    
    passed = 0
    failed = 0
    
    for url, expected_id, description in test_cases:
        print(f"\nTest: {description}")
        print(f"URL: {url}")
        
        # Extract video ID
        video_id = extract_youtube_video_id(url)
        print(f"Extracted ID: {video_id}")
        print(f"Expected ID: {expected_id}")
        
        # Validate
        is_valid, extracted_id, error_msg = validate_youtube_url(url)
        
        if video_id == expected_id and extracted_id == expected_id:
            print("✓ PASS")
            passed += 1
        else:
            print("✗ FAIL")
            if error_msg:
                print(f"Error: {error_msg}")
            failed += 1
        
        # Test helper functions if URL is valid
        if video_id:
            print(f"Is YouTube URL: {is_youtube_url(url)}")
            embed_url = get_youtube_embed_url(video_id)
            print(f"Embed URL: {embed_url}")
            thumbnail_url = get_youtube_thumbnail_url(video_id)
            print(f"Thumbnail: {thumbnail_url}")
    
    print("\n" + "=" * 60)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return passed, failed


if __name__ == '__main__':
    test_youtube_url_validation()
