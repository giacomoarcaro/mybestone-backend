import os
import logging
from pathlib import Path
from typing import List, Dict, Optional
import json
from datetime import datetime
import requests
from googleapiclient.discovery import build
from tqdm import tqdm
import yt_dlp
import time
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class YouTubeCollector:
    def __init__(self):
        self.api_key = os.getenv('YOUTUBE_API_KEY')
        if not self.api_key:
            raise ValueError("YouTube API key not found in environment variables")
        
        self.youtube = build('youtube', 'v3', developerKey=self.api_key)
        
        # Initialize directories
        self.videos_dir = Path("videos")
        self.videos_dir.mkdir(exist_ok=True)
        
        # Load already downloaded videos
        self.downloaded_videos = self._load_downloaded_videos()
        
        # API quota tracking
        self.daily_quota = 10000  # Free daily quota
        self.quota_used = 0
        self.last_reset = datetime.now()
    
    def _load_downloaded_videos(self) -> List[str]:
        """Load list of already downloaded videos."""
        downloaded_file = Path("downloaded_videos.json")
        if downloaded_file.exists():
            with open(downloaded_file, 'r') as f:
                return json.load(f)
        return []
    
    def _save_downloaded_videos(self):
        """Save list of downloaded videos."""
        with open("downloaded_videos.json", 'w') as f:
            json.dump(self.downloaded_videos, f)
    
    def _check_quota(self, cost: int) -> bool:
        """Check if we have enough quota for the operation."""
        # Reset quota if it's a new day
        if datetime.now().date() > self.last_reset.date():
            self.quota_used = 0
            self.last_reset = datetime.now()
        
        return (self.quota_used + cost) <= self.daily_quota
    
    def _use_quota(self, cost: int):
        """Use quota for an operation."""
        self.quota_used += cost
    
    def search_videos(self, query: str, max_results: int = 50) -> List[Dict]:
        """Search for videos using YouTube Data API."""
        try:
            if not self._check_quota(100):  # Search costs 100 units
                logger.warning("Daily quota limit reached")
                return []
            
            self._use_quota(100)
            
            # Search for videos
            search_response = self.youtube.search().list(
                q=query,
                part='id,snippet',
                maxResults=max_results,
                type='video',
                videoDuration='short'  # Only get short videos to save storage
            ).execute()
            
            videos = []
            for item in search_response.get('items', []):
                video_id = item['id']['videoId']
                if video_id not in self.downloaded_videos:
                    videos.append({
                        'id': video_id,
                        'title': item['snippet']['title'],
                        'description': item['snippet']['description'],
                        'published_at': item['snippet']['publishedAt']
                    })
            
            return videos
            
        except Exception as e:
            logger.error(f"Error searching videos: {str(e)}")
            return []
    
    def get_video_details(self, video_id: str) -> Optional[Dict]:
        """Get detailed information about a video."""
        try:
            if not self._check_quota(1):  # Video details cost 1 unit
                logger.warning("Daily quota limit reached")
                return None
            
            self._use_quota(1)
            
            video_response = self.youtube.videos().list(
                part='contentDetails,statistics',
                id=video_id
            ).execute()
            
            if not video_response['items']:
                return None
            
            return video_response['items'][0]
            
        except Exception as e:
            logger.error(f"Error getting video details: {str(e)}")
            return None
    
    def download_video(self, video_id: str) -> bool:
        """Download a video using yt-dlp."""
        try:
            video_path = self.videos_dir / f"{video_id}.mp4"
            
            if video_path.exists():
                return True
            
            ydl_opts = {
                'format': 'best[height<=720]',  # Limit to 720p to save storage
                'outtmpl': str(video_path),
                'quiet': True,
                'no_warnings': True
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([f'https://www.youtube.com/watch?v={video_id}'])
            
            return True
            
        except Exception as e:
            logger.error(f"Error downloading video {video_id}: {str(e)}")
            return False
    
    def collect_videos(self, query: str, max_videos: int = 100):
        """Collect videos based on search query."""
        try:
            logger.info(f"Starting video collection for query: {query}")
            
            # Search for videos
            videos = self.search_videos(query, max_videos)
            logger.info(f"Found {len(videos)} videos")
            
            # Download videos
            for video in tqdm(videos, desc="Downloading videos"):
                if len(self.downloaded_videos) >= max_videos:
                    break
                
                video_id = video['id']
                if video_id not in self.downloaded_videos:
                    if self.download_video(video_id):
                        self.downloaded_videos.append(video_id)
                        self._save_downloaded_videos()
                    
                    # Add delay between downloads to respect rate limits
                    time.sleep(1)
            
            logger.info(f"Total videos collected: {len(self.downloaded_videos)}")
            
        except Exception as e:
            logger.error(f"Error collecting videos: {str(e)}")

def main():
    # Example usage
    collector = YouTubeCollector()
    
    # Example search queries
    queries = [
        "nature timelapse",
        "city timelapse",
        "landscape timelapse"
    ]
    
    for query in queries:
        collector.collect_videos(query, max_videos=50)
        time.sleep(5)  # Delay between queries

if __name__ == "__main__":
    main() 