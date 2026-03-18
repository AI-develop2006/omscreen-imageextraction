# Om Screen Printing - Data Extraction System

An AI-powered web application designed to convert handwritten table images into structured Excel files efficiently.

## 🌟 Key Features
- **AI Extraction**: Uses Google Gemini AI to intelligently process handwritten rows and columns.
- **User Authentication**: Secure JWT-based signup and login system.
- **Editable Preview**: Verify and correct extracted data in a professional data grid before downloading.
- **Conversion History**: Access and re-edit your previous extractions at any time.
- **Premium Design**: Modern professional UI with glassmorphism, brand-specific animations, and soft-dark aesthetics.

## 🚀 Tech Stack
- **Frontend**: React.js, Vite, Tailwind CSS v4.
- **Backend**: FastAPI (Python), SQLite, Pydantic.
- **Security**: JWT Authentication, Bcrypt password hashing.
- **AI**: Google Generative AI (Gemini).

## 🛠️ Installation

### Backend Setup
1. Navigate to the `backend` directory.
2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: .\venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Set up environment variables in a `.env` file:
   ```env
   GEMINI_API_KEY=your_api_key_here
   SECRET_KEY=your_jwt_secret_key
   ```
5. Run the server:
   ```bash
   uvicorn main:app --reload
   ```

### Frontend Setup
1. Navigate to the `frontend` directory.
2. Install dependencies:
   ```bash
   npm install
   ```
3. Run the development server:
   ```bash
   npm run dev
   ```

## 📖 Usage
1. Sign up for a new account.
2. Upload a clear image of a handwritten table.
3. Review the extracted data in the preview grid.
4. Correct any errors and click **Save**.
5. Download your final **Excel (.xlsx)** file.

---
Developed for **Om Screen Printing**.
