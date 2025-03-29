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