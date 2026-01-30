"""
RAG (Retrieval Augmented Generation) Service.

Provides a unified interface for RAG operations used by both the Streamlit UI
and FastAPI service. Implements the ChatReadRetrieveRead pattern from
azure-search-openai-demo.

RAG Flow:
1. User Query → 
2. Azure AI Search (hybrid: vector + semantic) → 
3. Retrieved Documents → 
4. OpenAI (with context) → 
5. Response with citations
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, Generator, Any

from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizableTextQuery, QueryType

from .config import Settings, get_settings

logger = logging.getLogger(__name__)


# RAG System Prompt - based on azure-search-openai-demo pattern
RAG_SYSTEM_PROMPT = """You are an intelligent assistant helping users with questions based on the provided documents.
Answer ONLY with the facts listed in the sources below. If there isn't enough information below, say you don't know.
Do not generate answers that don't use the sources below. If asking a clarifying question would help, ask the question.

For tabular information return it as an html table. Do not return markdown format for tables.
Each source has a name followed by colon and the actual information, always include the source name for each fact you use in the response.
Use square brackets to reference the source, for example [source1.pdf]. Don't combine sources, list each source separately, for example [source1.pdf][source2.pdf].

{sources}
"""


@dataclass
class Document:
    """A retrieved document from the search index."""
    content: str
    title: str = ""
    source: str = ""
    page_number: int = 0
    score: float = 0.0
    reranker_score: float = 0.0


@dataclass
class RAGResponse:
    """Response from the RAG service."""
    answer: str
    documents: list[Document] = field(default_factory=list)
    sources_text: str = ""
    system_prompt: str = ""


class RAGService:
    """
    RAG (Retrieval Augmented Generation) Service.
    
    Provides a unified interface for:
    - Document retrieval from Azure AI Search
    - Response generation with Azure OpenAI
    - Source formatting and citation handling
    
    Usage:
        settings = get_settings()
        rag = RAGService(settings)
        
        # For complete response
        response = rag.chat("What is the deductible?")
        print(response.answer)
        
        # For streaming response
        for chunk in rag.chat_stream("What is the deductible?"):
            print(chunk, end="")
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        """
        Initialize the RAG service.
        
        Args:
            settings: Application settings. If None, loads from environment.
        """
        self.settings = settings or get_settings()
        self._openai_client: Optional[AzureOpenAI] = None
        self._search_client: Optional[SearchClient] = None
        self._credential: Optional[DefaultAzureCredential] = None
    
    @property
    def credential(self) -> DefaultAzureCredential:
        """Get or create Azure credential."""
        if self._credential is None:
            self._credential = DefaultAzureCredential()
        return self._credential
    
    @property
    def openai_client(self) -> AzureOpenAI:
        """Get or create Azure OpenAI client."""
        if self._openai_client is None:
            if not self.settings.azure_openai_endpoint:
                raise ValueError("AZURE_OPENAI_ENDPOINT environment variable not set")
            
            token_provider = get_bearer_token_provider(
                self.credential,
                "https://cognitiveservices.azure.com/.default"
            )
            
            self._openai_client = AzureOpenAI(
                azure_endpoint=self.settings.azure_openai_endpoint,
                azure_ad_token_provider=token_provider,
                api_version=self.settings.azure_openai_api_version
            )
        return self._openai_client
    
    @property
    def search_client(self) -> SearchClient:
        """Get or create Azure AI Search client."""
        if self._search_client is None:
            if not self.settings.azure_ai_search_endpoint:
                raise ValueError("AZURE_AI_SEARCH_ENDPOINT environment variable not set")
            
            self._search_client = SearchClient(
                endpoint=self.settings.azure_ai_search_endpoint,
                index_name=self.settings.azure_search_index_name,
                credential=self.credential
            )
        return self._search_client
    
    def search_documents(
        self,
        query: str,
        top_k: Optional[int] = None,
        use_semantic_ranker: Optional[bool] = None
    ) -> list[Document]:
        """
        Search the Azure AI Search index for relevant documents.
        
        Uses hybrid search (text + vector) with optional semantic ranking.
        
        Args:
            query: User's search query
            top_k: Number of results to return (defaults to settings)
            use_semantic_ranker: Whether to use semantic ranking (defaults to settings)
            
        Returns:
            List of relevant documents with content and metadata
        """
        top_k = top_k or self.settings.search_top_k
        use_semantic_ranker = use_semantic_ranker if use_semantic_ranker is not None else self.settings.use_semantic_ranker
        
        logger.info(f"🔍 RAG STEP 1: Searching for query: '{query}'")
        logger.info(f"   Index: {self.settings.azure_search_index_name}, Top K: {top_k}, Semantic Ranker: {use_semantic_ranker}")
        
        # Use vectorizable text query - the index has an integrated vectorizer
        vector_query = VectorizableTextQuery(
            text=query,
            k_nearest_neighbors=top_k,
            fields=self.settings.vector_field_name,
        )
        
        # Build search parameters based on azure-search-openai-demo pattern
        search_params = {
            "search_text": query,  # Keyword search
            "vector_queries": [vector_query],  # Vector search
            "top": top_k,
            "select": ["content", "title", "source", "page_number"],
        }
        
        # Add semantic ranking if enabled
        if use_semantic_ranker:
            search_params["query_type"] = QueryType.SEMANTIC
            search_params["semantic_configuration_name"] = self.settings.semantic_configuration_name
        
        try:
            results = self.search_client.search(**search_params)
            
            documents = []
            for result in results:
                documents.append(Document(
                    content=result.get("content", ""),
                    title=result.get("title", ""),
                    source=result.get("source", ""),
                    page_number=result.get("page_number", 0),
                    score=result.get("@search.score", 0),
                    reranker_score=result.get("@search.reranker_score", 0),
                ))
            
            logger.info(f"✅ RAG STEP 1 COMPLETE: Retrieved {len(documents)} documents")
            for i, doc in enumerate(documents):
                logger.info(f"   [{i+1}] {doc.source} - Score: {doc.score:.4f}")
            
            return documents
            
        except Exception as e:
            logger.error(f"❌ Search failed: {str(e)}")
            raise
    
    def format_sources_for_prompt(self, documents: list[Document]) -> str:
        """
        Format retrieved documents into sources string for the RAG prompt.
        
        Based on azure-search-openai-demo format: "sourcename: content"
        
        Args:
            documents: List of retrieved documents
            
        Returns:
            Formatted sources string for injection into system prompt
        """
        logger.info(f"📝 RAG STEP 2: Formatting {len(documents)} documents for prompt")
        
        if not documents:
            logger.warning("⚠️  No documents to format - sources will be empty")
            return "No sources available."
        
        sources = []
        for doc in documents:
            # Create source identifier
            source_name = doc.source or "unknown"
            if doc.page_number:
                source_name += f"#page={doc.page_number}"
            
            # Format: sourcename: content
            sources.append(f"{source_name}: {doc.content}")
        
        formatted = "\n\n".join(sources)
        logger.info(f"✅ RAG STEP 2 COMPLETE: Formatted sources ({len(formatted)} chars)")
        
        return formatted
    
    def format_citations_for_display(self, documents: list[Document]) -> str:
        """
        Format retrieved documents for display as citations.
        
        Args:
            documents: List of retrieved documents
            
        Returns:
            Formatted citations string for UI display
        """
        if not documents:
            return "No documents retrieved."
        
        citations = []
        for i, doc in enumerate(documents, 1):
            source_info = f"**{i}. {doc.title or 'Untitled'}**"
            if doc.source:
                source_info += f"\n   📄 {doc.source}"
            if doc.page_number:
                source_info += f" (Page {doc.page_number})"
            if doc.reranker_score:
                source_info += f"\n   🎯 Relevance: {doc.reranker_score:.2f}"
            citations.append(source_info)
        
        return "\n\n".join(citations)
    
    def build_messages(
        self,
        query: str,
        sources: str,
        conversation_history: Optional[list[dict]] = None,
        system_prompt: Optional[str] = None
    ) -> list[dict]:
        """
        Build the messages list for the OpenAI API call.
        
        Args:
            query: Current user query
            sources: Formatted sources string
            conversation_history: Previous messages in conversation
            system_prompt: Custom system prompt (uses default RAG prompt if None)
            
        Returns:
            List of message dicts for the OpenAI API
        """
        # Build system prompt with retrieved sources
        if system_prompt is None:
            system_prompt = RAG_SYSTEM_PROMPT
        
        system_message = system_prompt.format(sources=sources)
        
        logger.info("📋 RAG STEP 3: Building conversation messages")
        
        messages = [{"role": "system", "content": system_message}]
        
        # Add conversation history if provided
        if conversation_history:
            for msg in conversation_history:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
        
        # Add current user question
        messages.append({"role": "user", "content": query})
        
        return messages
    
    def generate_response(
        self,
        messages: list[dict],
        stream: bool = False,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> Any:
        """
        Generate a response from Azure OpenAI.
        
        Args:
            messages: List of message dicts for the API
            stream: Whether to stream the response
            max_tokens: Maximum tokens in response (defaults to settings)
            temperature: Sampling temperature (defaults to settings)
            
        Returns:
            OpenAI response object (streaming or complete)
        """
        deployment = self.settings.azure_openai_chat_deployment
        max_tokens = max_tokens or self.settings.max_tokens
        temperature = temperature if temperature is not None else self.settings.temperature
        
        logger.info(f"🤖 RAG STEP 4: Calling OpenAI model: {deployment}")
        logger.info(f"   Message count: {len(messages)}, Stream: {stream}")
        
        response = self.openai_client.chat.completions.create(
            model=deployment,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=stream
        )
        
        return response
    
    def chat(
        self,
        query: str,
        conversation_history: Optional[list[dict]] = None,
        top_k: Optional[int] = None,
        use_semantic_ranker: Optional[bool] = None
    ) -> RAGResponse:
        """
        Complete RAG chat flow: retrieve documents and generate response.
        
        This is the main method for non-streaming RAG interactions.
        
        Args:
            query: User's question
            conversation_history: Previous messages for multi-turn
            top_k: Number of documents to retrieve
            use_semantic_ranker: Whether to use semantic ranking
            
        Returns:
            RAGResponse with answer, documents, and metadata
        """
        logger.info("=" * 50)
        logger.info(f"📨 NEW USER QUERY: {query}")
        logger.info("=" * 50)
        
        # Step 1: Retrieve documents
        documents = self.search_documents(query, top_k, use_semantic_ranker)
        
        # Step 2: Format sources
        sources_text = self.format_sources_for_prompt(documents)
        
        # Step 3: Build messages
        system_prompt = RAG_SYSTEM_PROMPT.format(sources=sources_text)
        messages = self.build_messages(query, sources_text, conversation_history)
        
        # Step 4: Generate response
        response = self.generate_response(messages, stream=False)
        answer = response.choices[0].message.content
        
        return RAGResponse(
            answer=answer,
            documents=documents,
            sources_text=sources_text,
            system_prompt=system_prompt
        )
    
    def chat_stream(
        self,
        query: str,
        conversation_history: Optional[list[dict]] = None,
        top_k: Optional[int] = None,
        use_semantic_ranker: Optional[bool] = None
    ) -> Generator[tuple[str, Optional[RAGResponse]], None, None]:
        """
        Streaming RAG chat flow: retrieve documents and stream response.
        
        Yields chunks of the response as they're generated.
        The final yield includes the complete RAGResponse metadata.
        
        Args:
            query: User's question
            conversation_history: Previous messages for multi-turn
            top_k: Number of documents to retrieve
            use_semantic_ranker: Whether to use semantic ranking
            
        Yields:
            Tuples of (chunk_text, optional_final_response)
            The final_response is only populated on the last yield
        """
        logger.info("=" * 50)
        logger.info(f"📨 NEW USER QUERY (streaming): {query}")
        logger.info("=" * 50)
        
        # Step 1: Retrieve documents
        documents = self.search_documents(query, top_k, use_semantic_ranker)
        
        # Step 2: Format sources
        sources_text = self.format_sources_for_prompt(documents)
        
        # Step 3: Build messages
        system_prompt = RAG_SYSTEM_PROMPT.format(sources=sources_text)
        messages = self.build_messages(query, sources_text, conversation_history)
        
        # Step 4: Stream response
        response = self.generate_response(messages, stream=True)
        
        full_answer = ""
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                full_answer += content
                yield content, None
        
        # Final yield with complete metadata
        final_response = RAGResponse(
            answer=full_answer,
            documents=documents,
            sources_text=sources_text,
            system_prompt=system_prompt
        )
        yield "", final_response
    
    def get_documents_for_query(
        self,
        query: str,
        top_k: Optional[int] = None,
        use_semantic_ranker: Optional[bool] = None
    ) -> list[Document]:
        """
        Retrieve documents for a query without generating a response.
        
        Useful for document search functionality without LLM generation.
        
        Args:
            query: Search query
            top_k: Number of documents to retrieve
            use_semantic_ranker: Whether to use semantic ranking
            
        Returns:
            List of retrieved documents
        """
        return self.search_documents(query, top_k, use_semantic_ranker)
