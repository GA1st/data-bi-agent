import json
import re
from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agents.sql_agent import nl_to_sql, explain_result, fix_sql
from agents.chart_agent import suggest_chart
from agents.anomaly_agent import detect_anomalies
from services.query_executor import run_query
from core.session import sessions
from core.context import ContextManager, summarize_history
from config import settings
from core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

_ctx = ContextManager(max_tokens=settings.context_max_tokens)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    enable_anomaly: bool = False


class QuickQueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


_SESSION_RE = re.compile(r'^[a-zA-Z0-9_-]{1,64}$')


def _resolve_session(x_session_id: str | None = Header(None, alias="X-Session-ID")) -> str:
    sid = x_session_id or "default"
    if sid != "default" and not _SESSION_RE.match(sid):
        raise HTTPException(400, "Invalid session ID format")
    return sid


def _sse(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False) + "\n"


@router.post("")
async def chat_endpoint(
    req: ChatRequest,
    session_id: str = Depends(_resolve_session),
):
    if not req.message.strip():
        raise HTTPException(400, "消息不能为空")

    logger.info(f"Chat request from session {session_id[:8]}: {req.message[:50]}...")

    history = sessions.get_history(session_id)
    summary = sessions.get_summary(session_id)

    if _ctx.needs_summary(history, settings.context_summary_threshold):
        summary = await summarize_history(history)
        sessions.set_summary(session_id, summary)

    async def stream():
        yield _sse({"type": "status", "message": "正在分析您的问题..."})

        sql_result = await nl_to_sql(req.message, history, summary)
        if sql_result.get("error"):
            yield _sse({"type": "error", "message": sql_result["error"]})
            return

        sql = sql_result["sql"]
        explanation = sql_result.get("explanation", "")
        yield _sse({"type": "sql", "sql": sql, "explanation": explanation})
        yield _sse({"type": "status", "message": "正在执行查询..."})

        query_result = run_query(sql)
        if not query_result["success"]:
            fix_result = await fix_sql(sql, query_result["error"], req.message)
            if fix_result["sql"]:
                sql = fix_result["sql"]
                yield _sse({"type": "sql_fixed", "sql": sql, "explanation": fix_result.get("explanation", "")})
                query_result = run_query(sql)
                if not query_result["success"]:
                    yield _sse({"type": "error", "message": query_result["error"]})
                    return
            else:
                yield _sse({"type": "error", "message": query_result["error"]})
                return

        display_data = query_result["data"][:100]
        yield _sse({
            "type": "data",
            "data": display_data,
            "columns": query_result["columns"],
            "row_count": query_result["row_count"],
            "all_data": query_result["data"] if len(query_result["data"]) <= 500 else None,
        })

        chart_result = await suggest_chart(req.message, sql, query_result["data"], query_result["columns"])
        yield _sse({"type": "chart", "chart": chart_result})

        if req.enable_anomaly and len(query_result["data"]) > 2:
            anomaly_result = detect_anomalies(query_result["data"], query_result["columns"])
            yield _sse({"type": "anomaly", "anomaly": anomaly_result})

        explanation_text = await explain_result(req.message, sql, query_result["data"], query_result["columns"])
        yield _sse({"type": "explanation", "message": explanation_text})

        sessions.append(session_id, {"question": req.message, "sql": sql})
        logger.info(f"Chat completed: {query_result['row_count']} rows (model: heavy=NL2SQL, light=chart+explain)")

        yield _sse({"type": "done"})

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.post("/quick")
async def quick_query(req: QuickQueryRequest):
    sql_result = await nl_to_sql(req.question)
    if sql_result.get("error"):
        return {"success": False, "error": sql_result["error"]}

    query_result = run_query(sql_result["sql"])
    return {
        "success": query_result["success"],
        "sql": sql_result["sql"],
        "explanation": sql_result.get("explanation", ""),
        "data": query_result.get("data", []),
        "columns": query_result.get("columns", []),
    }


@router.get("/history")
async def get_history(session_id: str = Depends(_resolve_session)):
    return {
        "history": sessions.get_history(session_id)[-20:],
        "summary": sessions.get_summary(session_id),
    }


@router.delete("/history")
async def clear_history(session_id: str = Depends(_resolve_session)):
    sessions.clear(session_id)
    return {"message": "历史已清除"}
