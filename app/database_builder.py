import os
import cv2
import numpy as np
from pathlib import Path
import open_clip
import faiss
import json
from tqdm import tqdm
import torch
from PIL import Image
import logging
import shutil
from concurrent.futures import ThreadPoolExecutor
import gc

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseBuilder:
    def __init__(self):
        self.videos_dir = Path("videos")
        self.thumbnails_dir = Path("thumbnails")
        self.index_path = Path("faiss_index.bin")
        self.metadata_path = Path("metadata.json")
        self.temp_dir = Path("temp")
        
        # Create directories if they don't exist
        self.videos_dir.mkdir(exist_ok=True)
        self.thumbnails_dir.mkdir(exist_ok=True)
        self.temp_dir.mkdir(exist_ok=True)
        
        # Initialize CLIP model
        logger.info("Loading CLIP model...")
        self.model, _, self.preprocess = open_clip.create_model_and_transforms(
            'ViT-B-32', 
            pretrained='laion2b_s34b-b79k'
        )
        self.model.eval()
        
        # Initialize FAISS index
        self.dimension = 512  # CLIP embedding dimension
        self.index = faiss.IndexFlatL2(self.dimension)
        
        # Load existing metadata if exists
        self.metadata = []
        if self.metadata_path.exists():
            with open(self.metadata_path, 'r') as f:
                self.metadata = json.load(f)
                logger.info(f"Loaded {len(self.metadata)} existing entries")
        
        # Set batch size for processing
        self.batch_size = 32  # Adjust based on available memory
        
    def process_frame(self, frame, video_id: str, timestamp: float) -> dict:
        """Process a single frame and return metadata."""
        try:
            # Save thumbnail with compression
            thumbnail_path = self.thumbnails_dir / f"{video_id}_{timestamp:.2f}.jpg"
            cv2.imwrite(str(thumbnail_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            
            # Generate embedding
            img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            img = self.preprocess(img).unsqueeze(0)
            
            with torch.no_grad():
                embedding = self.model.encode_image(img).numpy()
            
            return {
                "thumbnail_path": str(thumbnail_path),
                "video_id": video_id,
                "timestamp": timestamp,
                "embedding": embedding.tolist()
            }
            
        except Exception as e:
            logger.error(f"Error processing frame: {str(e)}")
            return None
    
    def process_video(self, video_path: Path):
        """Process a single video file and extract thumbnails."""
        try:
            video_id = video_path.stem
            logger.info(f"Processing video: {video_id}")
            
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                logger.error(f"Could not open video: {video_path}")
                return
            
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = 0
            processed_frames = 0
            frames_batch = []
            
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Extract frame every 5 seconds
                if frame_count % int(fps * 5) == 0:
                    timestamp = frame_count / fps
                    frames_batch.append((frame, timestamp))
                    
                    # Process batch when it reaches batch_size
                    if len(frames_batch) >= self.batch_size:
                        self.process_batch(frames_batch, video_id)
                        frames_batch = []
                        processed_frames += self.batch_size
                
                frame_count += 1
            
            # Process remaining frames
            if frames_batch:
                self.process_batch(frames_batch, video_id)
                processed_frames += len(frames_batch)
            
            cap.release()
            logger.info(f"Processed {processed_frames} frames from {video_id}")
            
            # Clean up video file after processing
            video_path.unlink()
            
        except Exception as e:
            logger.error(f"Error processing video {video_path}: {str(e)}")
    
    def process_batch(self, frames_batch: list, video_id: str):
        """Process a batch of frames."""
        try:
            # Process frames in parallel
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = [
                    executor.submit(self.process_frame, frame, video_id, timestamp)
                    for frame, timestamp in frames_batch
                ]
                
                # Collect results
                for future in futures:
                    result = future.result()
                    if result:
                        # Add embedding to FAISS index
                        self.index.add(np.array(result["embedding"], dtype=np.float32))
                        # Store metadata without embedding
                        del result["embedding"]
                        self.metadata.append(result)
            
            # Clear memory
            gc.collect()
            
        except Exception as e:
            logger.error(f"Error processing batch: {str(e)}")
    
    def build_database(self):
        """Process all videos in the videos directory."""
        video_files = list(self.videos_dir.glob("*.mp4"))
        logger.info(f"Found {len(video_files)} videos to process")
        
        for video_path in tqdm(video_files, desc="Processing videos"):
            self.process_video(video_path)
            
            # Save progress after each video
            self.save_progress()
        
        logger.info(f"Database built successfully. Total entries: {len(self.metadata)}")
    
    def save_progress(self):
        """Save current progress."""
        try:
            # Save FAISS index
            faiss.write_index(self.index, str(self.index_path))
            
            # Save metadata
            with open(self.metadata_path, 'w') as f:
                json.dump(self.metadata, f)
                
        except Exception as e:
            logger.error(f"Error saving progress: {str(e)}")
    
    def verify_database(self):
        """Verify the integrity of the built database."""
        if not self.index_path.exists() or not self.metadata_path.exists():
            logger.error("Database files not found")
            return False
        
        try:
            # Load and verify FAISS index
            loaded_index = faiss.read_index(str(self.index_path))
            if loaded_index.ntotal != len(self.metadata):
                logger.error("Mismatch between index size and metadata entries")
                return False
            
            # Verify thumbnail files exist
            for entry in self.metadata:
                if not Path(entry["thumbnail_path"]).exists():
                    logger.error(f"Missing thumbnail: {entry['thumbnail_path']}")
                    return False
            
            logger.info("Database verification successful")
            return True
            
        except Exception as e:
            logger.error(f"Database verification failed: {str(e)}")
            return False
    
    def cleanup(self):
        """Clean up temporary files."""
        try:
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
            self.temp_dir.mkdir(exist_ok=True)
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")

if __name__ == "__main__":
    builder = DatabaseBuilder()
    try:
        builder.build_database()
        builder.verify_database()
    finally:
        builder.cleanup() 