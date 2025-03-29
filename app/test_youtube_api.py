from googleapiclient.discovery import build
from dotenv import load_dotenv
import os
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_youtube_api():
    """Test the YouTube Data API connection and quota."""
    try:
        # Load environment variables
        load_dotenv()
        api_key = os.getenv('YOUTUBE_API_KEY')
        
        if not api_key:
            logger.error("YouTube API key not found in environment variables")
            return
        
        # Initialize YouTube API client
        youtube = build('youtube', 'v3', developerKey=api_key)
        
        # Test 1: Simple search
        logger.info("Testing API with a simple search...")
        search_response = youtube.search().list(
            q='test',
            part='snippet',
            maxResults=1
        ).execute()
        
        if search_response.get('items'):
            logger.info("✓ Search test successful!")
            logger.info(f"Found video: {search_response['items'][0]['snippet']['title']}")
        else:
            logger.warning("No results found in search test")
        
        # Test 2: Get video details
        logger.info("\nTesting video details retrieval...")
        video_id = search_response['items'][0]['id']['videoId']
        video_response = youtube.videos().list(
            part='contentDetails,statistics',
            id=video_id
        ).execute()
        
        if video_response.get('items'):
            logger.info("✓ Video details test successful!")
            logger.info(f"Video duration: {video_response['items'][0]['contentDetails']['duration']}")
            logger.info(f"View count: {video_response['items'][0]['statistics']['viewCount']}")
        else:
            logger.warning("No video details found")
        
        logger.info("\nAll tests completed successfully!")
        
    except Exception as e:
        logger.error(f"Error testing YouTube API: {str(e)}")

if __name__ == "__main__":
    test_youtube_api() 