import uvicorn
from fastapi import FastAPI

from api import router

app = FastAPI(
    title="ADA Clinical Reasoning Engine v3",
    description="SaaS-ready CDS for diabetes management (ontology-driven)",
    version="3.0.0",
)

app.include_router(router)

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
