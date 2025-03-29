import os
import logging
from pathlib import Path
import numpy as np
import faiss
import json
import torch
from PIL import Image
import open_clip
from typing import List, Dict, Union
import cv2

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SearchEngine:
    def __init__(self):
        self.thumbnails_dir = Path("thumbnails")
        self.index_path = Path("faiss_index.bin")
        self.metadata_path = Path("metadata.json")
        
        # Load CLIP model
        logger.info("Loading CLIP model...")
        self.model, _, self.preprocess = open_clip.create_model_and_transforms(
            'ViT-B-32', 
            pretrained='laion2b_s34b-b79k'
        )
        self.model.eval()
        
        # Load FAISS index
        logger.info("Loading FAISS index...")
        self.index = faiss.read_index(str(self.index_path))
        
        # Load metadata
        logger.info("Loading metadata...")
        with open(self.metadata_path, 'r') as f:
            self.metadata = json.load(f)
        
        logger.info(f"Search engine initialized with {len(self.metadata)} entries")
    
    def _get_embedding(self, input_data: Union[str, np.ndarray]) -> np.ndarray:
        """Generate CLIP embedding from text or image."""
        try:
            if isinstance(input_data, str):
                # Text input
                text = open_clip.tokenize([input_data])
                with torch.no_grad():
                    embedding = self.model.encode_text(text).numpy()
            else:
                # Image input
                img = Image.fromarray(cv2.cvtColor(input_data, cv2.COLOR_BGR2RGB))
                img = self.preprocess(img).unsqueeze(0)
                with torch.no_grad():
                    embedding = self.model.encode_image(img).numpy()
            
            return embedding.astype('float32')
            
        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            raise
    
    def search(self, query: Union[str, np.ndarray], top_k: int = 10) -> List[Dict]:
        """Search for similar thumbnails using text or image query."""
        try:
            # Generate query embedding
            query_embedding = self._get_embedding(query)
            
            # Search FAISS index
            distances, indices = self.index.search(query_embedding, top_k)
            
            # Format results
            results = []
            for i, (distance, idx) in enumerate(zip(distances[0], indices[0])):
                if idx < len(self.metadata):
                    result = self.metadata[idx].copy()
                    # Convert distance to similarity score (0-1)
                    result['similarity_score'] = float(1 / (1 + distance))
                    results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(f"Error during search: {str(e)}")
            return []
    
    def get_thumbnail(self, thumbnail_path: str) -> np.ndarray:
        """Load a thumbnail image."""
        try:
            return cv2.imread(thumbnail_path)
        except Exception as e:
            logger.error(f"Error loading thumbnail {thumbnail_path}: {str(e)}")
            return None

def main():
    # Example usage
    engine = SearchEngine()
    
    # Example text search
    print("\nText search example:")
    results = engine.search("sunset over mountains", top_k=5)
    for result in results:
        print(f"Score: {result['similarity_score']:.3f}")
        print(f"Video: {result['video_id']}")
        print(f"Timestamp: {result['timestamp']:.2f}s")
        print("---")
    
    # Example image search
    print("\nImage search example:")
    # Load a sample image
    sample_image = cv2.imread("sample.jpg")  # Replace with your sample image
    if sample_image is not None:
        results = engine.search(sample_image, top_k=5)
        for result in results:
            print(f"Score: {result['similarity_score']:.3f}")
            print(f"Video: {result['video_id']}")
            print(f"Timestamp: {result['timestamp']:.2f}s")
            print("---")

if __name__ == "__main__":
    main() 