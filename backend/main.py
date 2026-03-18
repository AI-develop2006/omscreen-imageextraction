import os
import json
import uuid
import pandas as pd
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile, HTTPException, Form

load_dotenv()
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from google import genai

app = FastAPI(title="Handwritten to Excel Converter")

# Allow CORS for local frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

TEMP_DIR = "temp_files"
os.makedirs(TEMP_DIR, exist_ok=True)

@app.post("/api/convert")
async def convert_image_to_excel(
    file: UploadFile = File(...),
    api_key: Optional[str] = Form(None)
):
    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise HTTPException(status_code=400, detail="Gemini API Key is required. Please provide it in the input field or set 'GEMINI_API_KEY' environment variable.")

    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Uploaded file must be an image.")

    try:
        # Save uploaded image temporarily
        file_id = str(uuid.uuid4())
        image_ext = file.filename.split(".")[-1]
        image_path = os.path.join(TEMP_DIR, f"{file_id}.{image_ext}")
        excel_path = os.path.join(TEMP_DIR, f"{file_id}.xlsx")
        
        content = await file.read()
        with open(image_path, "wb") as f:
            f.write(content)

        # Initialize GenAI Client
        client = genai.Client(api_key=key)

        # Upload image to Gemini API
        gemini_file = client.files.upload(file=image_path)

        # Prompt for extracting tabular structure
        prompt = (
            "You are a highly capable data extraction AI. "
            "Please analyze the provided image. "
            "First, determine if the image contains handwritten or printed data that is structured in rows and columns (a table, log, list, etc.). "
            "If the image DOES NOT contain structured tabular data, return EXACTLY the following JSON: {\"error\": \"Image does not contain structured tabular data.\"} "
            "If it DOES contain structured tabular data, extract all text while preserving the exact row and column structure. "
            "Return the data strictly as a valid JSON array of objects. "
            "The keys of each object should be the column headers detected (e.g., 'S.No', 'Name', 'Salary', 'Date'). "
            "If there are no explicit headers, generate sensible ones like 'Column1', 'Column2', etc. "
            "Do not include any Markdown formatting like ```json ... ```, just pure JSON data."
        )

        # Call Gemini 2.5 Flash
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[gemini_file, prompt],
            config={"temperature": 0.1}
        )
        
        # Cleanup Gemini file
        client.files.delete(name=gemini_file.name)

        # Process the result
        response_text = response.text.replace("```json", "").replace("```", "").strip()
        
        try:
            data = json.loads(response_text)
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail=f"Failed to parse AI output into JSON. Raw response: {response_text[:100]}...")

        if isinstance(data, dict) and "error" in data:
            raise HTTPException(status_code=400, detail=data["error"])

        if not data or not isinstance(data, list):
            raise HTTPException(status_code=500, detail="AI output is empty or not in a standard table format.")

        # Convert to Pandas DataFrame and save to Excel
        df = pd.DataFrame(data)
        
        # Capitalize each word for string values
        for col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].apply(lambda x: x.title() if isinstance(x, str) else x)

        df.to_excel(excel_path, index=False)

        # Return the generated file
        return FileResponse(
            excel_path, 
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=f"converted_data_{file_id[:8]}.xlsx"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
