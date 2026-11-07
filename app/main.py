from fastapi import FastAPI

app = FastAPI(
    title="DocMind AI",
    description="AI-powered document assistant using RAG",
    version="0.1.0",
)


@app.get("/health")
def health_check():
    return {"status": "ok"}