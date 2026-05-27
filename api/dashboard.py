from fastapi import APIRouter
from agents.report_agent import generate_report
from core.database import get_table_names, get_table_columns, get_sample_data

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/report")
async def get_report(report_type: str = "daily"):
    report = await generate_report(report_type)
    return report


@router.get("/tables")
async def list_tables():
    tables = get_table_names()
    return {"tables": tables}


@router.get("/tables/{table_name}/schema")
async def table_schema(table_name: str):
    columns = get_table_columns(table_name)
    samples = get_sample_data(table_name, 5)
    return {"columns": columns, "sample_data": samples}
