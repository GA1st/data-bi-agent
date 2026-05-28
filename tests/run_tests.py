"""Test suite for Data BI Agent — run with: python tests/run_tests.py"""
import sys
import os
import json
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

passed = 0
failed = 0
errors = []


def test(name):
    def decorator(func):
        def wrapper():
            global passed, failed
            try:
                func()
                passed += 1
                print(f"  PASS  {name}")
            except Exception as e:
                failed += 1
                errors.append((name, str(e)))
                print(f"  FAIL  {name}: {e}")
        wrapper._name = name
        return wrapper
    return decorator


# ============================================================
# Config tests
# ============================================================
@test("config: Settings loads defaults")
def test_config_defaults():
    from config import settings
    assert settings.app_port == 8000
    assert settings.debug is True
    assert settings.llm_model == "gpt-4"
    assert settings.llm_model_small == "gpt-4o-mini"
    assert settings.cache_enabled is True
    assert settings.auth_enabled is False


@test("config: context settings present")
def test_config_context():
    from config import settings
    assert settings.context_max_tokens == 8000
    assert settings.context_summary_threshold == 12


# ============================================================
# Exceptions tests
# ============================================================
@test("exceptions: hierarchy works")
def test_exceptions():
    from core.exceptions import AppError, DatabaseError, ValidationError, AuthError
    try:
        raise DatabaseError("db broken")
    except AppError as e:
        assert e.status_code == 500
        assert e.error_code == "DATABASE_ERROR"
        assert "db broken" in e.detail

    try:
        raise ValidationError("bad input")
    except AppError as e:
        assert e.status_code == 400


# ============================================================
# Logger tests
# ============================================================
@test("logger: setup and get_logger")
def test_logger():
    from core.logger import setup_logging, get_logger
    setup_logging()
    logger = get_logger("test")
    assert logger is not None
    logger.info("test log message")


# ============================================================
# Cache tests
# ============================================================
@test("cache: TTLCache set/get/delete")
def test_cache_basic():
    from core.cache import TTLCache
    c = TTLCache(ttl=60, max_size=10)
    c.set("k1", {"val": 123})
    assert c.get("k1") == {"val": 123}
    assert c.get("missing") is None
    c.delete("k1")
    assert c.get("k1") is None


@test("cache: TTL expiry")
def test_cache_ttl():
    from core.cache import TTLCache
    c = TTLCache(ttl=1, max_size=10)
    c.set("k", "v")
    assert c.get("k") == "v"
    time.sleep(1.5)
    assert c.get("k") is None


@test("cache: max_size eviction")
def test_cache_eviction():
    from core.cache import TTLCache
    c = TTLCache(ttl=60, max_size=3)
    c.set("a", 1)
    c.set("b", 2)
    c.set("c", 3)
    c.set("d", 4)  # should evict oldest
    assert c.get("a") is None
    assert c.get("d") == 4


# ============================================================
# Context manager tests
# ============================================================
@test("context: token estimation")
def test_token_estimation():
    from core.context import estimate_tokens
    t1 = estimate_tokens("你好世界")
    t2 = estimate_tokens("SELECT * FROM orders")
    t3 = estimate_tokens("")
    assert t1 > 0
    assert t2 > 0
    assert t3 == 0


@test("context: build_messages with history")
def test_context_build():
    from core.context import ContextManager
    ctx = ContextManager(max_tokens=2000)
    history = [
        {"question": "本月销售额", "sql": "SELECT SUM(amount) FROM orders"},
        {"question": "各区域排名", "sql": "SELECT region FROM orders GROUP BY region"},
    ]
    msgs = ctx.build_messages("System prompt", history, "哪个产品最畅销")
    assert msgs[0]["role"] == "system"
    assert msgs[-1]["role"] == "user"
    assert "最畅销" in msgs[-1]["content"]
    assert len(msgs) >= 5  # system + 2*2 history + current


@test("context: budget trimming works with tight budget")
def test_context_budget():
    from core.context import ContextManager
    # With 10 history items and a tight budget, some should be trimmed
    ctx = ContextManager(max_tokens=400)
    big_history = [
        {"question": f"第{i}个查询：请帮我分析销售数据排名情况", "sql": f"SELECT region, SUM(total_amount) as total FROM orders GROUP BY region ORDER BY total DESC LIMIT {i*10}"}
        for i in range(10)
    ]
    msgs = ctx.build_messages("你是专业的数据分析师和SQL专家，请根据schema生成查询。", big_history, "哪个产品最畅销")
    history_msgs = [m for m in msgs if m["role"] in ("user", "assistant")]
    # 10 history pairs = 20 messages. With 400 token budget, should be less.
    assert len(history_msgs) < 20, f"Expected trimming, got {len(history_msgs)} history msgs"


@test("context: needs_summary detection")
def test_needs_summary():
    from core.context import ContextManager
    ctx = ContextManager()
    assert ctx.needs_summary([{}] * 15, threshold=12) is True
    assert ctx.needs_summary([{}] * 5, threshold=12) is False


# ============================================================
# Session tests
# ============================================================
@test("session: create, append, get, clear")
def test_session():
    from core.session import SessionManager
    sm = SessionManager(max_sessions=5)
    sm.append("s1", {"q": "test", "sql": "SELECT 1"})
    sm.append("s1", {"q": "test2", "sql": "SELECT 2"})
    h = sm.get_history("s1")
    assert len(h) == 2
    sm.clear("s1")
    assert len(sm.get_history("s1")) == 0


@test("session: LRU eviction")
def test_session_lru():
    from core.session import SessionManager
    sm = SessionManager(max_sessions=2)
    sm.get_history("s1")
    sm.get_history("s2")
    sm.get_history("s3")  # should evict s1
    assert sm.active_sessions == 2


@test("session: summary storage")
def test_session_summary():
    from core.session import SessionManager
    sm = SessionManager()
    sm.set_summary("s1", "这是一个摘要")
    assert sm.get_summary("s1") == "这是一个摘要"
    assert sm.get_summary("s99") is None


# ============================================================
# Database tests
# ============================================================
@test("database: init and query")
def test_database_basic():
    from core.database import init_db, execute_query, execute_update, get_table_names
    init_db()
    tables = get_table_names()
    assert len(tables) > 0
    rows = execute_query("SELECT COUNT(*) as cnt FROM orders")
    assert rows[0]["cnt"] > 0


@test("database: identifier validation")
def test_identifier_validation():
    from core.database import _validate_identifier
    assert _validate_identifier("orders") == "orders"
    assert _validate_identifier("order_items") == "order_items"
    try:
        _validate_identifier("DROP TABLE")
        assert False, "Should have raised"
    except Exception:
        pass


@test("database: schema caching")
def test_schema_cache():
    from core.database import get_full_schema
    from core.cache import cache
    s1 = get_full_schema()
    s2 = get_full_schema()
    assert s1 == s2
    assert len(s1) > 100


# ============================================================
# Query executor tests
# ============================================================
@test("query_executor: validation blocks non-SELECT")
def test_query_validation():
    from services.query_executor import validate_sql
    ok, msg = validate_sql("DROP TABLE orders")
    assert ok is False
    ok, msg = validate_sql("DELETE FROM orders WHERE 1=1")
    assert ok is False
    ok, msg = validate_sql("")
    assert ok is False


@test("query_executor: validation allows SELECT and WITH")
def test_query_validation_pass():
    from services.query_executor import validate_sql
    ok, _ = validate_sql("SELECT * FROM orders")
    assert ok is True
    ok, _ = validate_sql("WITH cte AS (SELECT 1) SELECT * FROM cte")
    assert ok is True


@test("query_executor: run_query executes safely")
def test_run_query():
    from services.query_executor import run_query
    result = run_query("SELECT 1 as num, 'hello' as msg")
    assert result["success"] is True
    assert result["data"][0]["num"] == 1
    assert result["columns"] == ["num", "msg"]


@test("query_executor: run_query blocks dangerous SQL")
def test_run_query_blocked():
    from services.query_executor import run_query
    result = run_query("DROP TABLE orders")
    assert result["success"] is False
    assert "不允许" in result["error"]


@test("query_executor: auto LIMIT added")
def test_query_limit():
    from services.query_executor import run_query
    result = run_query("SELECT * FROM orders")
    assert result["success"] is True
    assert "LIMIT" in result["sql"]


# ============================================================
# LLM model routing tests
# ============================================================
@test("llm: model downgrade routing")
def test_model_routing():
    from core.llm import _resolve_model
    from config import settings
    assert _resolve_model(None, "heavy") == settings.llm_model
    assert _resolve_model(None, "light") == settings.llm_model_small
    assert _resolve_model("custom", "heavy") == "custom"


# ============================================================
# Anomaly detection tests
# ============================================================
@test("anomaly: detect outliers")
def test_anomaly_detection():
    from agents.anomaly_agent import detect_anomalies
    data = [
        {"name": "a", "value": 10},
        {"name": "b", "value": 12},
        {"name": "c", "value": 11},
        {"name": "d", "value": 9},
        {"name": "e", "value": 500},  # outlier
    ]
    result = detect_anomalies(data, ["name", "value"])
    assert result["has_anomaly"] is True
    assert result["anomaly_count"] > 0


@test("anomaly: no outliers in normal data")
def test_anomaly_normal():
    from agents.anomaly_agent import detect_anomalies
    data = [{"name": f"r{i}", "value": i * 10} for i in range(20)]
    result = detect_anomalies(data, ["name", "value"])
    assert isinstance(result["has_anomaly"], bool)


# ============================================================
# Run all tests
# ============================================================
def run_all():
    global passed, failed, errors
    print("=" * 60)
    print("Data BI Agent — Test Suite")
    print("=" * 60)

    # Collect all test functions from this module
    current_module = sys.modules[__name__]
    tests = [getattr(current_module, name) for name in dir(current_module)
             if callable(getattr(current_module, name)) and hasattr(getattr(current_module, name), '_name')]

    start = time.time()
    for t in tests:
        t()
    elapsed = time.time() - start

    print("-" * 60)
    print(f"Results: {passed} passed, {failed} failed ({elapsed:.2f}s)")
    if errors:
        print("\nFailures:")
        for name, err in errors:
            print(f"  {name}: {err}")
    print("=" * 60)
    return failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
