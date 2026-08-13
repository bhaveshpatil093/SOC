from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routers import analytics, overview, behavior, anomalies, threats, sigma, investigations, entities

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

app.include_router(analytics.router)
app.include_router(overview.router)
app.include_router(behavior.router)
app.include_router(anomalies.router)
app.include_router(threats.router)
app.include_router(sigma.router)
app.include_router(investigations.router)
app.include_router(entities.router)

@app.get("/")
def root():
    return {"message": "SOC Analytics API is running"}
