# MyBestOne Backend

A FastAPI backend service for the MyBestOne video search application.

## Local Development

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the development server:
```bash
uvicorn app.main:app --reload
```

## Deployment on Render.com

### Prerequisites

1. Create a [Render.com](https://render.com) account
2. Push your code to a GitHub repository
3. Make sure you have the following files in your repository:
   - `requirements.txt`
   - `render.yaml`
   - `.renderignore`
   - Your FastAPI application code

### Deployment Steps

1. **Connect to GitHub**
   - Log in to your Render.com account
   - Click "New +" and select "Web Service"
   - Connect your GitHub repository
   - Select the repository containing this backend code

2. **Configure the Web Service**
   - Name: `mybestone-backend`
   - Environment: `Python`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - Python Version: 3.10.0

3. **Set Environment Variables**
   - Add the following environment variables in Render dashboard:
     - `SECRET_KEY`: Your secret key for JWT tokens
     - `ALGORITHM`: HS256
     - `ACCESS_TOKEN_EXPIRE_MINUTES`: 30

4. **Deploy**
   - Click "Create Web Service"
   - Render will automatically deploy your application
   - Once deployed, you'll get a URL like `https://mybestone-backend.onrender.com`

### Important Notes

- The first deployment might take longer due to the compilation of `faiss-cpu`
- Make sure your frontend application is configured to use the new backend URL
- Monitor the deployment logs in Render dashboard for any issues
- The free tier of Render has some limitations, consider upgrading for production use

## API Documentation

Once deployed, you can access the API documentation at:
- Swagger UI: `https://your-app.onrender.com/docs`
- ReDoc: `https://your-app.onrender.com/redoc`

## Environment Variables

Required environment variables:
- `SECRET_KEY`: Secret key for JWT token generation
- `ALGORITHM`: JWT algorithm (default: HS256)
- `ACCESS_TOKEN_EXPIRE_MINUTES`: Token expiration time in minutes (default: 30) 