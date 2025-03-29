import logging
from pathlib import Path
from video_collector import VideoCollector
from database_builder import DatabaseBuilder

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def build_mvp_database():
    """Build the MVP database by collecting videos and processing them."""
    try:
        # Step 1: Collect videos
        logger.info("Step 1: Collecting videos...")
        collector = VideoCollector()
        
        # Add your video URLs here
        # You can get these from various sources:
        # 1. Public domain video repositories
        # 2. Creative Commons licensed content
        # 3. Your own video collection
        urls = [
            # Add your video URLs here
            # Example:
            # "https://example.com/video1.mp4",
            # "https://example.com/video2.mp4"
        ]
        
        collector.collect_videos(urls)
        
        # Step 2: Process videos and build database
        logger.info("Step 2: Processing videos and building database...")
        builder = DatabaseBuilder()
        builder.build_database()
        
        # Step 3: Verify database
        logger.info("Step 3: Verifying database...")
        if builder.verify_database():
            logger.info("MVP database built successfully!")
        else:
            logger.error("Database verification failed!")
            
    except Exception as e:
        logger.error(f"Error building MVP database: {str(e)}")
        raise

if __name__ == "__main__":
    build_mvp_database() 