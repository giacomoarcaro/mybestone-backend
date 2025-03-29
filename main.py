from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from typing import Optional, List
import os
from dotenv import load_dotenv
import uvicorn
from app.youtube_collector import YouTubeCollector
from app.video_collector import VideoCollector
from app.models import User, Token, TokenData, VideoResult

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="MyBestOne API",
    description="API for video search and collection",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Initialize collectors
youtube_collector = YouTubeCollector()
video_collector = VideoCollector()

@app.get("/", response_model=dict)
async def root():
    """Root endpoint that returns the API status"""
    return {
        "status": "Backend is running",
        "version": "1.0"
    }

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
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
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = User.get_user(username=token_data.username)
    if user is None:
        raise credentials_exception
    return user

@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = User.authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/search", response_model=List[VideoResult])
async def search_videos(
    query: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user)
):
    try:
        if image:
            # Handle image search
            results = await video_collector.search_by_image(image)
        elif query:
            # Handle text search
            results = await youtube_collector.search_by_text(query)
        else:
            raise HTTPException(status_code=400, detail="Either query or image must be provided")
        
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/collect-videos")
async def start_video_collection(
    background_tasks: BackgroundTasks,
    max_videos: int = 10000,
    current_user: User = Depends(get_current_user)
):
    """Start the video collection process in the background"""
    try:
        background_tasks.add_task(youtube_collector.collect_videos, max_videos)
        return {"message": "Video collection started successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/collection-status")
async def get_collection_status(current_user: User = Depends(get_current_user)):
    """Get the current status of video collection"""
    try:
        total_videos = len(youtube_collector.videos)
        return {
            "total_videos": total_videos,
            "status": "in_progress" if total_videos < 10000 else "completed"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 