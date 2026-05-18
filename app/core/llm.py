from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from app.core.config import settings


def get_groq_llm(temperature=0.0):
    """Returns a ChatGroq instance. Useful for fast, structured routing and tool calling."""
    return ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model_name="llama-3.3-70b-versatile",
        temperature=temperature
    )


def get_gemini_llm(temperature=0.0):
    """Returns a Gemini 2.0 Flash instance. Used for complex reasoning and RAG."""
    return ChatGoogleGenerativeAI(
        google_api_key=settings.GEMINI_API_KEY,
        model="gemini-2.0-flash",
        temperature=temperature,
    )


def get_gemini_flash_llm(temperature=0.0):
    """Returns a Gemini 2.0 Flash instance for fast, capable responses."""
    return ChatGoogleGenerativeAI(
        google_api_key=settings.GEMINI_API_KEY,
        model="gemini-2.0-flash",
        temperature=temperature,
    )


def get_embeddings():
    """Returns the Google Generative AI Embeddings model."""
    return GoogleGenerativeAIEmbeddings(
        google_api_key=settings.GEMINI_API_KEY,
        model="models/gemini-embedding-001"
    )
