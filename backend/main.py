import os
import json
import uuid
import pandas as pd
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
import database

load_dotenv()

# Security Configuration
SECRET_KEY = os.environ.get("SECRET_KEY", "your-secret-key-change-this-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 # 24 hours

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/login")

app = FastAPI(title="Handwritten to Excel Converter")
database.init_db()

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
    return user

# --- Middleware ---

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
    file: UploadFile = File(...),
    api_key: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user)
):
    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise HTTPException(status_code=400, detail="Gemini API Key is required.")

    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Uploaded file must be an image.")

    try:
        file_id = str(uuid.uuid4())
        image_ext = file.filename.split(".")[-1]
        image_path = os.path.join(TEMP_DIR, f"{file_id}.{image_ext}")
        excel_path = os.path.join(TEMP_DIR, f"{file_id}.xlsx")
        
        content = await file.read()
        with open(image_path, "wb") as f:
            f.write(content)

        client = genai.Client(api_key=key)
        gemini_file = client.files.upload(file=image_path)

        prompt = (
            "You are a highly capable data extraction AI. "
            "Please analyze the provided image. "
            "If the image DOES NOT contain structured tabular data, return EXACTLY the following JSON: {\"error\": \"Image does not contain structured tabular data.\"} "
            "If it DOES contain structured tabular data, extract all text while preserving the exact row and column structure. "
            "Return the data strictly as a valid JSON array of objects. "
            "The keys of each object should be the column headers detected (e.g., 'S.No', 'Name', 'Salary', 'Date'). "
            "If there are no explicit headers, generate sensible ones like 'Column1', 'Column2', etc. "
            "Do not include any Markdown formatting like ```json ... ```, just pure JSON data."
        )

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[gemini_file, prompt],
            config={"temperature": 0.1}
        )
        client.files.delete(name=gemini_file.name)

        response_text = response.text.replace("```json", "").replace("```", "").strip()
        
        try:
            data = json.loads(response_text)
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail=f"Failed to parse AI output into JSON.")

        if isinstance(data, dict) and "error" in data:
            raise HTTPException(status_code=400, detail=data["error"])

        if not data or not isinstance(data, list):
            raise HTTPException(status_code=500, detail="AI output is not in a standard table format.")

        df = pd.DataFrame(data)
        for col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].apply(lambda x: x.title() if isinstance(x, str) else x)

        excel_filename = f"converted_data_{file_id[:8]}.xlsx"
        df.to_excel(excel_path, index=False)
        
        database.add_conversion(file_id, current_user["id"], file.filename, excel_filename, json.dumps(data))

        return {"id": file_id, "data": data, "filename": file.filename}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/history")
async def get_history(current_user: dict = Depends(get_current_user)):
    try:
        return database.get_all_conversions(current_user["id"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/preview/{file_id}")
async def get_preview(file_id: str, current_user: dict = Depends(get_current_user)):
    record = database.get_conversion(file_id)
    if not record or record["user_id"] != current_user["id"]:
        raise HTTPException(status_code=404, detail="Conversion not found")
    
    return {
        "id": record["id"],
        "data": json.loads(record["data"]),
        "filename": record["original_filename"]
    }

@app.post("/api/save/{file_id}")
async def save_changes(file_id: str, payload: SaveData, current_user: dict = Depends(get_current_user)):
    record = database.get_conversion(file_id)
    if not record or record["user_id"] != current_user["id"]:
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
async def download_file(file_id: str, current_user: dict = Depends(get_current_user)):
    record = database.get_conversion(file_id)
    if not record or record["user_id"] != current_user["id"]:
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
        filename=record["excel_filename"]
    )
