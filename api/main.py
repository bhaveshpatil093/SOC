from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from api.routers import analytics, overview, behavior, anomalies, threats, sigma, investigations, entities, search, reports

app = FastAPI(
    title="SOC Analytics API",
    description="Read-only API for SOC Next.js Frontend",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow frontend access for dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Log the full exception to the console for developers
    print(f"Error handling request {request.method} {request.url}: {exc}")
    # Return a sanitized error to the client
    return JSONResponse(
        status_code=500,
        content={"error": "Internal analytics engine failure. The dataset may be currently processing or offline."}
    )

app.include_router(analytics.router)
app.include_router(overview.router)
app.include_router(behavior.router)
app.include_router(anomalies.router)
app.include_router(threats.router)
app.include_router(sigma.router)
app.include_router(investigations.router)
app.include_router(entities.router)
app.include_router(search.router)
app.include_router(reports.router)

@app.get("/")
def root():
    return {"message": "SOC Analytics API is running"}
