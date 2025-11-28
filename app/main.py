from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from app.utils import Output, DocumentService, QdrantService


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Initializing services...")
    doc_service = DocumentService()
    docs = doc_service.create_documents()
    print(f"Loaded {len(docs)} documents.")

    qdrant_service = QdrantService()
    qdrant_service.connect()
    qdrant_service.load(docs)
    print("Qdrant service connected and documents loaded.")
    app.state.qdrant_service = qdrant_service

    yield {"qdrant_service": qdrant_service}

app = FastAPI(lifespan=lifespan)

# Add CORS to allow requests from the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def get_qdrant_service(request: Request) -> QdrantService:
    return request.app.state.qdrant_service


@app.get("/query", response_model=Output)
async def query(q: str = Query(..., description="Input question", max_length=1024),
                qdrant_service: QdrantService = Depends(get_qdrant_service)):
    return qdrant_service.query(q)
