from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from datetime import datetime, timedelta
from typing import List, Optional
import os
import json
from pathlib import Path
import numpy as np
import faiss
import open_clip
import cv2
from PIL import Image
import io
from pydantic import BaseModel
from jose import JWTError, jwt
from passlib.context import CryptContext

# Initialize FastAPI app
app = FastAPI(title="MyBestOne API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://mybestone-frontend.vercel.app",
        "https://mybestone-frontend-hxojvi85l-giacomos-projects-0cd87d4e.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Paths
VIDEOS_DIR = Path("videos")
THUMBNAILS_DIR = Path("thumbnails")
INDEX_PATH = Path("faiss_index.bin")
METADATA_PATH = Path("metadata.json")

# Create directories if they don't exist
VIDEOS_DIR.mkdir(exist_ok=True)
THUMBNAILS_DIR.mkdir(exist_ok=True)

# Initialize CLIP model
model, _, preprocess = open_clip.create_model_and_transforms('ViT-B-32', pretrained='laion2b_s34b-b79k')
model.eval()

# Initialize FAISS index
DIMENSION = 512  # CLIP embedding dimension
index = faiss.IndexFlatL2(DIMENSION)

# Load metadata if exists
metadata = []
if METADATA_PATH.exists():
    with open(METADATA_PATH, 'r') as f:
        metadata = json.load(f)

class User(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None
    is_premium: bool = False
    searches_remaining: int = 5
    last_search_reset: str = datetime.now().isoformat()

class Token(BaseModel):
    access_token: str
    token_type: str

class SearchResult(BaseModel):
    thumbnail_path: str
    video_id: str
    timestamp: float
    similarity_score: float

# User management (in-memory for demo)
users_db = {}

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = users_db.get(username)
    if user is None:
        raise credentials_exception
    return user

@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = users_db.get(form_data.username)
    if not user or not pwd_context.verify(form_data.password, user.get("hashed_password")):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user["username"]})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/register")
async def register(user: User):
    if user.username in users_db:
        raise HTTPException(status_code=400, detail="Username already registered")
    hashed_password = pwd_context.hash("default_password")  # In production, use proper password
    users_db[user.username] = {
        "username": user.username,
        "hashed_password": hashed_password,
        "is_premium": user.is_premium,
        "searches_remaining": user.searches_remaining,
        "last_search_reset": user.last_search_reset
    }
    return {"message": "User created successfully"}

@app.post("/search")
async def search(
    query: str = None,
    image: UploadFile = File(None),
    current_user: User = Depends(get_current_user)
):
    # Check search limits
    if not current_user.is_premium:
        if current_user.searches_remaining <= 0:
            last_reset = datetime.fromisoformat(current_user.last_search_reset)
            if datetime.now() - last_reset > timedelta(days=1):
                current_user.searches_remaining = 5
                current_user.last_search_reset = datetime.now().isoformat()
            else:
                raise HTTPException(
                    status_code=429,
                    detail="Daily search limit reached. Upgrade to premium for unlimited searches."
                )
        current_user.searches_remaining -= 1

    # Generate embedding from query
    if image:
        # Process uploaded image
        contents = await image.read()
        img = Image.open(io.BytesIO(contents))
        img = preprocess(img).unsqueeze(0)
        with torch.no_grad():
            query_embedding = model.encode_image(img).numpy()
    else:
        # Process text query
        text = open_clip.tokenize([query])
        with torch.no_grad():
            query_embedding = model.encode_text(text).numpy()

    # Search FAISS index
    D, I = index.search(query_embedding.astype('float32'), 10)
    
    # Format results
    results = []
    for i, (distance, idx) in enumerate(zip(D[0], I[0])):
        if idx < len(metadata):
            result = metadata[idx]
            result['similarity_score'] = float(1 / (1 + distance))  # Convert distance to similarity score
            results.append(SearchResult(**result))

    return results

@app.post("/upgrade")
async def upgrade_to_premium(current_user: User = Depends(get_current_user)):
    # In production, integrate with Stripe here
    current_user.is_premium = True
    return {"message": "Successfully upgraded to premium"}

# Initialize the system
@app.on_event("startup")
async def startup_event():
    # Load FAISS index if exists
    if INDEX_PATH.exists():
        index = faiss.read_index(str(INDEX_PATH))
    
    # Process videos if thumbnails don't exist
    if not any(THUMBNAILS_DIR.iterdir()):
        process_videos()

def process_videos():
    """Extract thumbnails and generate embeddings for all videos"""
    for video_path in VIDEOS_DIR.glob("*.mp4"):
        video_id = video_path.stem
        cap = cv2.VideoCapture(str(video_path))
        fps = cap.get(cv2.CAP_PROP_FPS)
        
        frame_count = 0
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
                
            if frame_count % int(fps * 5) == 0:  # Extract frame every 5 seconds
                timestamp = frame_count / fps
                thumbnail_path = THUMBNAILS_DIR / f"{video_id}_{timestamp:.2f}.jpg"
                
                # Save thumbnail
                cv2.imwrite(str(thumbnail_path), frame)
                
                # Generate embedding
                img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                img = preprocess(img).unsqueeze(0)
                with torch.no_grad():
                    embedding = model.encode_image(img).numpy()
                
                # Add to FAISS index
                index.add(embedding.astype('float32'))
                
                # Store metadata
                metadata.append({
                    "thumbnail_path": str(thumbnail_path),
                    "video_id": video_id,
                    "timestamp": timestamp
                })
            
            frame_count += 1
        cap.release()
    
    # Save FAISS index and metadata
    faiss.write_index(index, str(INDEX_PATH))
    with open(METADATA_PATH, 'w') as f:
        json.dump(metadata, f) 