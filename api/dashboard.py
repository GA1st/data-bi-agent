from fastapi import APIRouter, HTTPException

from agents.report_agent import generate_report
from core.database import (
    _validate_identifier,
    get_sample_data,
    get_table_columns,
    get_table_names,
)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

VALID_REPORT_TYPES = {"daily", "weekly", "monthly"}


@router.get("/report")
async def get_report(report_type: str = "daily"):
    if report_type not in VALID_REPORT_TYPES:
        raise HTTPException(400, f"Invalid report type. Valid: {VALID_REPORT_TYPES}")
    report = await generate_report(report_type)
    return report


@router.get("/tables")
async def list_tables():
    tables = get_table_names()
    return {"tables": tables}


@router.get("/tables/{table_name}/schema")
async def table_schema(table_name: str):
    try:
        safe = _validate_identifier(table_name)
    except Exception:
        raise HTTPException(400, f"Invalid table name: {table_name}") from None
    columns = get_table_columns(safe)
    samples = get_sample_data(safe, 5)
    return {"columns": columns, "sample_data": samples}
