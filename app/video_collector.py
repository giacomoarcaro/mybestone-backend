import os
import requests
import time
from pathlib import Path
import logging
from typing import List, Optional
import json
from urllib.parse import urlparse
import aiohttp
import asyncio
from tqdm import tqdm
import tempfile
from fastapi import UploadFile
import cv2
import numpy as np
from datetime import datetime
from .models import VideoResult

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VideoCollector:
    def __init__(self):
        self.videos_dir = Path("videos")
        self.videos_dir.mkdir(exist_ok=True)
        self.downloaded_videos = set()
        self.load_downloaded_videos()
        
    def load_downloaded_videos(self):
        """Load list of already downloaded videos."""
        downloaded_file = self.videos_dir / "downloaded_videos.json"
        if downloaded_file.exists():
            with open(downloaded_file, 'r') as f:
                self.downloaded_videos = set(json.load(f))
    
    def save_downloaded_videos(self):
        """Save list of downloaded videos."""
        downloaded_file = self.videos_dir / "downloaded_videos.json"
        with open(downloaded_file, 'w') as f:
            json.dump(list(self.downloaded_videos), f)
    
    async def download_video(self, url: str, session: aiohttp.ClientSession) -> Optional[str]:
        """Download a single video file."""
        try:
            # Generate filename from URL
            parsed_url = urlparse(url)
            filename = os.path.basename(parsed_url.path)
            if not filename.endswith('.mp4'):
                filename = f"{filename}.mp4"
            
            # Skip if already downloaded
            if filename in self.downloaded_videos:
                return None
            
            # Download video
            async with session.get(url) as response:
                if response.status == 200:
                    filepath = self.videos_dir / filename
                    with open(filepath, 'wb') as f:
                        while True:
                            chunk = await response.content.read(8192)
                            if not chunk:
                                break
                            f.write(chunk)
                    
                    self.downloaded_videos.add(filename)
                    return str(filepath)
                else:
                    logger.error(f"Failed to download {url}: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error downloading {url}: {str(e)}")
            return None
    
    async def download_videos_async(self, urls: List[str], max_concurrent: int = 5):
        """Download multiple videos concurrently."""
        async with aiohttp.ClientSession() as session:
            # Process URLs in chunks to limit concurrent downloads
            for i in range(0, len(urls), max_concurrent):
                chunk = urls[i:i + max_concurrent]
                tasks = [self.download_video(url, session) for url in chunk]
                results = await asyncio.gather(*tasks)
                
                # Add delay between chunks to respect rate limits
                if i + max_concurrent < len(urls):
                    await asyncio.sleep(2)
    
    def collect_videos(self, urls: List[str]):
        """Collect videos from provided URLs."""
        logger.info(f"Starting video collection from {len(urls)} URLs")
        
        # Run async download
        asyncio.run(self.download_videos_async(urls))
        
        # Save progress
        self.save_downloaded_videos()
        
        # Print summary
        total_downloaded = len(self.downloaded_videos)
        logger.info(f"Video collection complete. Total videos: {total_downloaded}")

    async def search_by_image(self, image: UploadFile) -> List[VideoResult]:
        try:
            # Save uploaded image to temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
                content = await image.read()
                temp_file.write(content)
                temp_file_path = temp_file.name

            # Read and process the image
            img = cv2.imread(temp_file_path)
            if img is None:
                raise ValueError("Failed to read uploaded image")

            # TODO: Implement actual image similarity search
            # For now, return dummy results
            results = [
                VideoResult(
                    video_id="dummy1",
                    title="Sample Video 1",
                    description="This is a sample video description",
                    thumbnail_path="https://via.placeholder.com/320x180",
                    similarity_score=0.95,
                    published_at=datetime.now(),
                    channel_title="Sample Channel"
                ),
                VideoResult(
                    video_id="dummy2",
                    title="Sample Video 2",
                    description="Another sample video description",
                    thumbnail_path="https://via.placeholder.com/320x180",
                    similarity_score=0.85,
                    published_at=datetime.now(),
                    channel_title="Sample Channel"
                )
            ]

            # Clean up temporary file
            os.unlink(temp_file_path)

            return results

        except Exception as e:
            print(f"Error processing image: {str(e)}")
            raise

def main():
    # Example usage
    collector = VideoCollector()
    
    # Example URLs (replace with your actual video sources)
    urls = [
        # Add your video URLs here
        # Example:
        # "https://example.com/video1.mp4",
        # "https://example.com/video2.mp4"
    ]
    
    collector.collect_videos(urls)

if __name__ == "__main__":
    main() 