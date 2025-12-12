# Paper Agent

A modern, intelligent paper management system with powerful search, chat, and analysis capabilities.

## ✨ Features

- 📚 **Paper Library**: Browse, search, and manage your academic papers
- 💬 **AI Chat**: Have intelligent conversations about your papers
- ⚙️ **Data Management**: Import CSV files and process PDFs
- 🔧 **Flexible Configuration**: Customize LLM and embedding models

## 🚀 Quick Start

### Backend Setup

```bash
cd backend
pip install -r requirements.txt

# Initialize database and import papers
python -m backend.scripts.import_csv /path/to/library.csv

# Start the backend server
uvicorn backend.app.main:app --reload --port 8000
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Visit `http://localhost:5173` to access the application.

## 📁 Project Structure

```
SuperPaperAgent/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI application
│   │   ├── models.py        # Database models
│   │   ├── db.py            # Database connection
│   │   ├── routers/         # API endpoints
│   │   └── services/        # Business logic
│   └── scripts/
│       ├── import_csv.py    # Import papers from CSV
│       ├── process_pdfs.py  # Extract text from PDFs
│       ├── embed_chunks.py  # Generate embeddings
│       └── summarize_papers.py  # Generate summaries
└── frontend/
    ├── src/
    │   ├── pages/           # Page components
    │   │   ├── PapersPage.tsx
    │   │   ├── ChatPage.tsx
    │   │   ├── ManagementPage.tsx
    │   │   └── SettingsPage.tsx
    │   ├── components/      # Reusable components
    │   ├── styles/          # Global styles
    │   └── App.tsx          # Main app with routing
    └── package.json

```

## 🎨 New UI Features

The frontend has been completely redesigned with:

- **Modern Navigation**: Sidebar navigation with clear page separation
- **Dedicated Pages**:
  - Papers: Browse and view paper details
  - Chat: Have conversations with AI about papers
  - Management: Import data and run processing pipelines
  - Settings: Configure API endpoints and models
- **Improved Layout**: Cleaner, more spacious design with better organization
- **Dark Theme**: Beautiful dark mode with gradient accents
- **Responsive**: Works on desktop and mobile devices

## 🛠️ Backend Scripts

### Import Papers
```bash
python -m backend.scripts.import_csv path/to/library.csv --limit 100
```

### Process PDFs
```bash
python -m backend.scripts.process_pdfs --chunk-size 1200 --overlap 200
```

### Generate Embeddings
```bash
python -m backend.scripts.embed_chunks --batch-size 50
```

### Generate Summaries
```bash
python -m backend.scripts.summarize_papers --batch-size 10
```

## 📝 Configuration

Configure LLM and embedding models through the Settings page or by setting these keys in the database:

- `LLM_BASE_URL`: Base URL for the LLM API
- `LLM_MODEL`: Model name for chat and summarization
- `LLM_API_KEY`: API key for LLM service
- `EMBED_BASE_URL`: Base URL for embedding API
- `EMBED_MODEL`: Model name for embeddings
- `EMBED_API_KEY`: API key for embedding service

## 🔧 Development

### Frontend Development
```bash
cd frontend
npm run dev
```

### Backend Development
```bash
cd backend
uvicorn backend.app.main:app --reload --port 8000
```

### Build for Production
```bash
cd frontend
npm run build
```

## 📄 License

MIT License

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

