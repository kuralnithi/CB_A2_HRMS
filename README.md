# AI HRMS Copilot - Backend

This is the backend service for the AI HRMS Copilot project, built with FastAPI, PostgreSQL, and Langchain.

## 🌟 Overview

The backend acts as the core brain of the HRMS, providing secure REST APIs for frontend consumption and housing the advanced AI Copilot processing engine. 

### ✨ Key Features
- **FastAPI Core**: High-performance, asynchronous REST APIs.
- **JWT Authentication**: Secure role-based access control (Admin, Manager, Employee).
- **PostgreSQL Database**: Relational mapping using SQLAlchemy ORM for robust data integrity.
- **AI Processing Engine**: Integration with LLMs (OpenAI) via Langchain for dynamic natural language processing.
- **Retrieval-Augmented Generation (RAG)**: Context-aware document retrieval for answering specific company HR policies.

---

## 🏗️ System Architecture & Overall Flow

```mermaid
sequenceDiagram
    participant User
    participant NextJS as Next.js Frontend
    participant FastAPI as FastAPI Backend
    participant Auth as Auth Middleware
    participant DB as PostgreSQL
    participant AI as AI Engine

    User->>NextJS: Perform Action (e.g. view leaves)
    NextJS->>FastAPI: API Request with JWT Token
    FastAPI->>Auth: Validate JWT
    
    alt Invalid Token
        Auth-->>FastAPI: Unauthorized
        FastAPI-->>NextJS: 401 Error
        NextJS-->>User: Redirect to Login
    else Valid Token
        Auth-->>FastAPI: User Payload (ID, Role)
        FastAPI->>DB: Execute Query (ORM)
        DB-->>FastAPI: Data Result
        FastAPI-->>NextJS: JSON Response
        NextJS-->>User: Update UI
    end
```

---

## 🤖 AI Copilot Workflow

The backend handles the heavy lifting for the AI Copilot. When a user asks a question, the backend classifies the intent, queries relevant internal data, and constructs an augmented prompt for the LLM.

```mermaid
flowchart TD
    A[Frontend Chat API Call] --> B[FastAPI Endpoint: /api/v1/chat]
    B --> C[Extract User Intent & Context]
    
    C --> D{Is it a Data/Action Request?}
    D -->|Yes: E.g., 'Book a leave'| E[Query DB for current limits/status]
    D -->|No: E.g., 'What is the remote policy?'| F[Vector Search / RAG]
    
    F --> G[(Policy Documents DB)]
    G --> H[Retrieve Top Similar Contexts]
    
    E --> I[Construct Final Prompt]
    H --> I
    
    I --> J[OpenAI / LLM API]
    J -->|Stream/Process| K[Generate AI Response]
    K --> L[Format Markdown & Sources]
    L --> M[Return to Frontend]
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.9+
- PostgreSQL
- OpenAI API Key

### Installation

1. Clone the repository and navigate to the backend folder.
2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Set up your `.env` file:
   ```env
   DATABASE_URL=postgresql://user:password@localhost:5432/ai_hrms
   SECRET_KEY=your_super_secret_key
   OPENAI_API_KEY=sk-...
   ```
5. Run the database migrations (if applicable) and start the server:
   ```bash
   uvicorn main:app --reload
   ```

The API will be available at [http://127.0.0.1:8000](http://127.0.0.1:8000) with Swagger documentation at `/docs`.
