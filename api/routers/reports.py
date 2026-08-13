from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uuid
import os
import time
import pandas as pd
import json

from api.services.data_service import get_scored_events

router = APIRouter(prefix="/api/v1/reports", tags=["Reports"])

# In-memory storage for reports
REPORTS_DB = {}
REPORTS_DIR = "/tmp/soc_reports"

# Ensure reports directory exists
os.makedirs(REPORTS_DIR, exist_ok=True)

class ReportRequest(BaseModel):
    name: str
    report_type: str
    format: str # 'csv', 'json'
    severity: Optional[str] = None
    host: Optional[str] = None
    user: Optional[str] = None
    time_range: Optional[str] = "30d"

class ReportResponse(BaseModel):
    id: str
    name: str
    report_type: str
    format: str
    status: str
    created_at: str
    filters: dict

def generate_report_task(report_id: str, request: ReportRequest):
    """Background task to generate the report."""
    try:
        # Simulate processing delay
        time.sleep(3)
        
        df = get_scored_events()
        if df is None or df.empty:
            raise ValueError("No data available")

        # Apply filters
        filtered_df = df.copy()
        if request.severity and request.severity.lower() != "all":
            filtered_df = filtered_df[filtered_df["threat_level"] == request.severity]
        if request.host:
            filtered_df = filtered_df[filtered_df["host.hostname"] == request.host]
        if request.user:
            filtered_df = filtered_df[filtered_df["user.name"] == request.user]
        
        # Depending on report type, we might select specific columns
        if request.report_type == "Overview":
            cols = ["@timestamp", "event.action", "user.name", "host.hostname", "threat_level"]
            filtered_df = filtered_df[[c for c in cols if c in filtered_df.columns]]
        elif request.report_type == "Anomaly":
            cols = ["@timestamp", "anomaly_score", "threat_level", "user.name", "host.hostname", "event.action"]
            filtered_df = filtered_df[[c for c in cols if c in filtered_df.columns]]
            filtered_df = filtered_df[filtered_df["is_anomaly"] == True]
        elif request.report_type == "Threat":
            cols = ["@timestamp", "anomaly_score", "threat_level", "user.name", "host.hostname", "mitre_technique"]
            filtered_df = filtered_df[[c for c in cols if c in filtered_df.columns]]
            filtered_df = filtered_df[filtered_df["threat_level"].isin(["High Threat", "Critical"])]
        
        # Export
        file_path = os.path.join(REPORTS_DIR, f"{report_id}.{request.format.lower()}")
        if request.format.lower() == "csv":
            filtered_df.to_csv(file_path, index=False)
        elif request.format.lower() == "json":
            filtered_df.to_json(file_path, orient="records", date_format="iso")
        else:
            raise ValueError("Unsupported format")
        
        REPORTS_DB[report_id]["status"] = "completed"
        
    except Exception as e:
        print(f"Report generation failed: {e}")
        if report_id in REPORTS_DB:
            REPORTS_DB[report_id]["status"] = "failed"

@router.post("", response_model=ReportResponse)
def create_report(request: ReportRequest, background_tasks: BackgroundTasks):
    report_id = str(uuid.uuid4())
    
    report_record = {
        "id": report_id,
        "name": request.name,
        "report_type": request.report_type,
        "format": request.format,
        "status": "processing",
        "created_at": datetime.now().isoformat(),
        "filters": {
            "severity": request.severity,
            "host": request.host,
            "user": request.user,
            "time_range": request.time_range
        }
    }
    
    REPORTS_DB[report_id] = report_record
    
    background_tasks.add_task(generate_report_task, report_id, request)
    
    return report_record

@router.get("", response_model=List[ReportResponse])
def list_reports():
    # Return sorted by created_at descending
    reports = list(REPORTS_DB.values())
    reports.sort(key=lambda x: x["created_at"], reverse=True)
    return reports

@router.get("/{report_id}/download")
def download_report(report_id: str):
    if report_id not in REPORTS_DB:
        raise HTTPException(status_code=404, detail="Report not found")
        
    report = REPORTS_DB[report_id]
    if report["status"] != "completed":
        raise HTTPException(status_code=400, detail="Report not ready")
        
    file_path = os.path.join(REPORTS_DIR, f"{report_id}.{report['format'].lower()}")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Report file missing")
        
    filename = f"{report['name'].replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.{report['format'].lower()}"
    return FileResponse(path=file_path, filename=filename, media_type="application/octet-stream")
