"""
FastAPI REST API for Azure OpenAI Chat

Provides REST endpoints for programmatic access to Azure OpenAI chat functionality.
Uses managed identity authentication when deployed to Azure App Service.
"""

import os
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider


# Global client instance
openai_client: Optional[AzureOpenAI] = None


def get_openai_client() -> AzureOpenAI:
    """
    Create Azure OpenAI client using managed identity.
    """
    global openai_client
    
    if openai_client is None:
        endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
        if not endpoint:
            raise ValueError("AZURE_OPENAI_ENDPOINT environment variable not set")
        
        token_provider = get_bearer_token_provider(
            DefaultAzureCredential(),
            "https://cognitiveservices.azure.com/.default"
        )
        
        openai_client = AzureOpenAI(
            azure_endpoint=endpoint,
            azure_ad_token_provider=token_provider,
            api_version="2024-10-21"
        )
    
    return openai_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources on startup."""
    # Initialize OpenAI client on startup
    try:
        get_openai_client()
        print("Azure OpenAI client initialized successfully")
    except Exception as e:
        print(f"Warning: Failed to initialize OpenAI client: {e}")
    yield
    # Cleanup on shutdown
    global openai_client
    openai_client = None


# FastAPI app
app = FastAPI(
    title="Azure OpenAI Chat API",
    description="REST API for chat interactions with Azure OpenAI",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response Models
class Message(BaseModel):
    """A chat message."""
    role: str = Field(..., description="Message role: 'user', 'assistant', or 'system'")
    content: str = Field(..., description="Message content")


class ChatRequest(BaseModel):
    """Chat request payload."""
    message: str = Field(..., description="The user's message")
    conversation_history: list[Message] = Field(
        default=[],
        description="Previous messages in the conversation for context"
    )
    system_prompt: str = Field(
        default="You are a helpful AI assistant. Provide clear, accurate, and helpful responses.",
        description="System prompt to guide the assistant's behavior"
    )
    max_tokens: int = Field(default=2048, ge=1, le=4096, description="Maximum tokens in response")
    temperature: float = Field(default=0.7, ge=0, le=2, description="Sampling temperature")


class ChatResponse(BaseModel):
    """Chat response payload."""
    response: str = Field(..., description="The assistant's response")
    model: str = Field(..., description="Model used for completion")
    usage: dict = Field(..., description="Token usage statistics")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    endpoint_configured: bool
    model: str


# API Endpoints
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Azure OpenAI Chat API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Health check endpoint.
    
    Returns the service status and configuration state.
    """
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    model = os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o-mini")
    
    return HealthResponse(
        status="healthy",
        endpoint_configured=bool(endpoint),
        model=model
    )


@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(request: ChatRequest):
    """
    Send a message and receive a complete response.
    
    This endpoint waits for the full response before returning.
    Use /chat/stream for streaming responses.
    """
    try:
        client = get_openai_client()
        deployment = os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o-mini")
        
        # Build messages list
        messages = [{"role": "system", "content": request.system_prompt}]
        
        # Add conversation history
        for msg in request.conversation_history:
            messages.append({"role": msg.role, "content": msg.content})
        
        # Add current user message
        messages.append({"role": "user", "content": request.message})
        
        # Call Azure OpenAI
        response = client.chat.completions.create(
            model=deployment,
            messages=messages,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            stream=False
        )
        
        return ChatResponse(
            response=response.choices[0].message.content,
            model=response.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
        )
        
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat completion failed: {str(e)}")


@app.post("/chat/stream", tags=["Chat"])
async def chat_stream(request: ChatRequest):
    """
    Send a message and receive a streaming response.
    
    Returns a Server-Sent Events (SSE) stream with response chunks.
    """
    try:
        client = get_openai_client()
        deployment = os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o-mini")
        
        # Build messages list
        messages = [{"role": "system", "content": request.system_prompt}]
        
        # Add conversation history
        for msg in request.conversation_history:
            messages.append({"role": msg.role, "content": msg.content})
        
        # Add current user message
        messages.append({"role": "user", "content": request.message})
        
        async def generate():
            response = client.chat.completions.create(
                model=deployment,
                messages=messages,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                stream=True
            )
            
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    yield f"data: {content}\n\n"
            
            yield "data: [DONE]\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
        
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat completion failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
