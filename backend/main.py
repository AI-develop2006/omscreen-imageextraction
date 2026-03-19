import os
import json
import uuid
import pandas as pd
import shutil
from datetime import datetime, timedelta
from typing import Optional, List
from dotenv import load_dotenv

from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Depends, status
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from jose import JWTError, jwt
from passlib.context import CryptContext
from google import genai
from google.genai import types
import time
import database

load_dotenv()

# --- Config & Singletons ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")

# Initialize Gemini Client as a singleton
genai_client = None
if GEMINI_API_KEY:
    genai_client = genai.Client(api_key=GEMINI_API_KEY)

# Security Configuration
SECRET_KEY = os.environ.get("SECRET_KEY", "your-secret-key-change-this-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 # 24 hours

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/login")

app = FastAPI(title="Handwritten to Excel - Production API")
database.init_db()

# --- Health Check ---
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

# --- Models ---

class UserCreate(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class User(BaseModel):
    id: str
    username: str

class SaveData(BaseModel):
    data: List[dict]

# --- Security Helpers ---

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
        status_code=status.HTTP_401_UNAUTHORIZED,
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
    user = database.get_user_by_username(username)
    if user is None:
        raise credentials_exception
    # Convert dict to User model for type safety
    return User(id=user["id"], username=user["username"])

# --- Middleware ---

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

TEMP_DIR = "temp_files"
os.makedirs(TEMP_DIR, exist_ok=True)

# --- Auth Endpoints ---

@app.post("/api/signup")
async def signup(user_in: UserCreate):
    existing_user = database.get_user_by_username(user_in.username)
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    user_id = str(uuid.uuid4())
    hashed_password = get_password_hash(user_in.password)
    database.add_user(user_id, user_in.username, hashed_password)
    
    return {"status": "success", "message": "User created successfully"}

@app.post("/api/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = database.get_user_by_username(form_data.username)
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# --- Core Endpoints ---

@app.post("/api/convert")
async def convert_image_to_excel(
    files: List[UploadFile] = File(...),
    api_key: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user)
):
    if len(files) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 files allowed.")
    
    all_extracted_data = []
    original_filenames = [f.filename for f in files]
    primary_filename = original_filenames[0]
    rate_limit_hit = False
    
    # Initialize client (prefer provided key, then singleton)
    client = genai_client
    if api_key:
        client = genai.Client(api_key=api_key)
    
    if not client:
        raise HTTPException(status_code=400, detail="Gemini API key is missing.")
    
    for file in files:
        file_id = str(uuid.uuid4())
        extension = file.filename.split('.')[-1]
        temp_path = os.path.join(TEMP_DIR, f"{file_id}.{extension}")
        
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        try:
            # Prepare image for Gemini
            with open(temp_path, "rb") as f:
                image_data = f.read()
            
            # Gemini Prompt for Table Extraction
            prompt = """
            Analyze the attached image and extract all tabular data.
            Return the data ONLY as a JSON list of objects, where each object represents a row.
            Use the column headers found in the image as keys.
            If no headers are clear, use 'Column1', 'Column2', etc.
            Ensure every row in the table is captured.
            Do not include any explanation, markdown formatting, or text outside the JSON list.
            """
            
            # Retry Logic for Gemini API
            max_retries = 3
            retry_count = 0
            backoff_time = 2  # Initial backoff in seconds
            extracted_data = None
            
            while retry_count <= max_retries:
                try:
                    response = client.models.generate_content(
                        model="gemini-2.0-flash",
                        contents=[
                            prompt,
                            types.Part.from_bytes(data=image_data, mime_type=file.content_type)
                        ]
                    )
                    
                    content = response.text.strip()
                    # Clean possible markdown formatting
                    if content.startswith("```json"):
                        content = content[7:-3].strip()
                    elif content.startswith("```"):
                        content = content[3:-3].strip()
                    
                    extracted_data = json.loads(content)
                    break # Success!
                    
                except Exception as e:
                    error_msg = str(e).lower()
                    if "429" in error_msg or "resource_exhausted" in error_msg:
                        rate_limit_hit = True
                        retry_count += 1
                        if retry_count > max_retries:
                            print(f"Max retries reached for {file.filename} due to rate limits.")
                            raise # Re-raise to be caught by the outer loop's exception handler
                        
                        print(f"Rate limit hit for {file.filename}. Retrying in {backoff_time}s... (Attempt {retry_count}/{max_retries})")
                        time.sleep(backoff_time)
                        backoff_time *= 2 # Exponential backoff
                    else:
                        print(f"Error during Gemini API call for {file.filename}: {e}")
                        raise # Re-raise other errors
            
            if extracted_data and isinstance(extracted_data, list):
                # Add a 'Source File' column to distinguish data
                for row in extracted_data:
                    row["_source"] = file.filename
                all_extracted_data.extend(extracted_data)
            
        except Exception as e:
            print(f"Error processing {file.filename}: {e}")
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                rate_limit_hit = True
            continue # Skip failed files but continue batch
            
    if not all_extracted_data:
        if rate_limit_hit:
            raise HTTPException(status_code=429, detail="Gemini API rate limit exceeded. Please wait a minute and try again.")
        raise HTTPException(status_code=500, detail="Failed to extract data from any of the uploaded images.")

    # Save to database
    db_id = str(uuid.uuid4())
    excel_filename = f"converted_data_{db_id[:8]}.xlsx"
    
    # Pre-generate the Excel file for immediate download availability
    excel_path = os.path.join(TEMP_DIR, f"{db_id}.xlsx")
    df = pd.DataFrame(all_extracted_data)
    df.to_excel(excel_path, index=False)
    
    database.add_conversion(db_id, current_user.id, primary_filename, excel_filename, json.dumps(all_extracted_data))
    
    return {
        "id": db_id,
        "filename": primary_filename,
        "data": all_extracted_data,
        "count": len(files)
    }

@app.get("/api/history")
async def get_history(current_user: User = Depends(get_current_user)):
    try:
        return database.get_all_conversions(current_user.id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/preview/{file_id}")
async def get_preview(file_id: str, current_user: User = Depends(get_current_user)):
    record = database.get_conversion(file_id)
    if not record or record["user_id"] != current_user.id:
        raise HTTPException(status_code=404, detail="Conversion not found")
    
    return {
        "id": record["id"],
        "data": json.loads(record["data"]),
        "filename": record["original_filename"]
    }

@app.post("/api/save/{file_id}")
async def save_changes(file_id: str, payload: SaveData, current_user: User = Depends(get_current_user)):
    record = database.get_conversion(file_id)
    if not record or record["user_id"] != current_user.id:
        raise HTTPException(status_code=404, detail="Conversion not found")
    
    database.update_conversion_data(file_id, json.dumps(payload.data))
    
    try:
        excel_path = os.path.join(TEMP_DIR, f"{file_id}.xlsx")
        df = pd.DataFrame(payload.data)
        df.to_excel(excel_path, index=False)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to regenerate Excel: {str(e)}")
    
    return {"status": "success", "message": "Changes saved"}

@app.get("/api/download/{file_id}")
async def download_file(file_id: str, current_user: User = Depends(get_current_user)):
    record = database.get_conversion(file_id)
    if not record or record["user_id"] != current_user.id:
        raise HTTPException(status_code=404, detail="Record not found")

    excel_path = os.path.join(TEMP_DIR, f"{file_id}.xlsx")
    if not os.path.exists(excel_path):
        try:
            data = json.loads(record["data"])
            df = pd.DataFrame(data)
            df.to_excel(excel_path, index=False)
        except:
            raise HTTPException(status_code=404, detail="File could not be found")
        
    return FileResponse(
        excel_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"converted_{record['original_filename'].split('.')[0]}.xlsx"
    )
