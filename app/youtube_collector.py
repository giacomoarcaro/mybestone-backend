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
from .models import VideoResult
import asyncio

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class YouTubeCollector:
    def __init__(self):
        self.api_key = os.getenv("YOUTUBE_API_KEY")
        if not self.api_key:
            raise ValueError("YOUTUBE_API_KEY environment variable is not set")
        self.youtube = build('youtube', 'v3', developerKey=self.api_key)
        self.data_dir = Path("data")
        self.data_dir.mkdir(exist_ok=True)
        self.videos_file = self.data_dir / "videos.json"
        self.load_existing_videos()

    def load_existing_videos(self):
        """Load existing videos from JSON file"""
        if self.videos_file.exists():
            with open(self.videos_file, 'r') as f:
                self.videos = json.load(f)
        else:
            self.videos = {}

    def save_videos(self):
        """Save videos to JSON file"""
        with open(self.videos_file, 'w') as f:
            json.dump(self.videos, f, indent=2)

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
                if video_id not in self.videos:
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
    
    async def collect_videos(self, max_videos: int = 10000):
        """Collect videos from YouTube with rate limiting"""
        try:
            # Keywords to search for
            keywords = [
                "cooking", "gaming", "music", "sports", "education",
                "entertainment", "news", "tech", "travel", "fashion"
            ]

            videos_collected = 0
            for keyword in keywords:
                if videos_collected >= max_videos:
                    break

                logger.info(f"Collecting videos for keyword: {keyword}")
                next_page_token = None

                while videos_collected < max_videos:
                    try:
                        # Search for videos
                        search_response = self.youtube.search().list(
                            q=keyword,
                            part='id,snippet',
                            maxResults=50,
                            type='video',
                            pageToken=next_page_token
                        ).execute()

                        # Get video details
                        video_ids = [item['id']['videoId'] for item in search_response['items']]
                        videos_response = self.youtube.videos().list(
                            part='snippet,statistics,contentDetails',
                            id=','.join(video_ids)
                        ).execute()

                        # Process videos
                        for video in videos_response['items']:
                            if video['id'] not in self.videos:
                                self.videos[video['id']] = {
                                    'title': video['snippet']['title'],
                                    'description': video['snippet']['description'],
                                    'thumbnail_path': video['snippet']['thumbnails']['high']['url'],
                                    'published_at': video['snippet']['publishedAt'],
                                    'channel_title': video['snippet']['channelTitle'],
                                    'duration': video['contentDetails']['duration'],
                                    'view_count': video['statistics'].get('viewCount', '0'),
                                    'like_count': video['statistics'].get('likeCount', '0'),
                                    'comment_count': video['statistics'].get('commentCount', '0')
                                }
                                videos_collected += 1
                                logger.info(f"Collected {videos_collected} videos")

                                # Save progress every 100 videos
                                if videos_collected % 100 == 0:
                                    self.save_videos()

                        # Get next page token
                        next_page_token = search_response.get('nextPageToken')
                        if not next_page_token:
                            break

                        # Rate limiting
                        time.sleep(1)  # Wait 1 second between requests

                    except Exception as e:
                        logger.error(f"Error collecting videos for keyword {keyword}: {str(e)}")
                        time.sleep(5)  # Wait longer on error
                        continue

            # Final save
            self.save_videos()
            logger.info(f"Video collection complete. Total videos: {videos_collected}")

        except Exception as e:
            logger.error(f"Error in video collection: {str(e)}")
            raise

    async def search_by_text(self, query: str) -> List[VideoResult]:
        try:
            # Search for videos
            search_response = self.youtube.search().list(
                q=query,
                part='id,snippet',
                maxResults=10,
                type='video'
            ).execute()

            # Get video details
            video_ids = [item['id']['videoId'] for item in search_response['items']]
            videos_response = self.youtube.videos().list(
                part='snippet,statistics',
                id=','.join(video_ids)
            ).execute()

            # Format results
            results = []
            for video in videos_response['items']:
                result = VideoResult(
                    video_id=video['id'],
                    title=video['snippet']['title'],
                    description=video['snippet']['description'],
                    thumbnail_path=video['snippet']['thumbnails']['high']['url'],
                    similarity_score=1.0,  # Text search doesn't have similarity scores
                    published_at=datetime.fromisoformat(video['snippet']['publishedAt'].replace('Z', '+00:00')),
                    channel_title=video['snippet']['channelTitle']
                )
                results.append(result)

            return results

        except Exception as e:
            logger.error(f"Error searching YouTube: {str(e)}")
            raise

def main():
    # Example usage
    collector = YouTubeCollector()
    asyncio.run(collector.collect_videos(max_videos=10000))

if __name__ == "__main__":
    main() 