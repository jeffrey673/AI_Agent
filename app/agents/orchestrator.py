"""Orchestrator Agent (v3.0 core).

v2.0: Query Analyzer -> route_type -> single Agent call
v3.0: Orchestrator(Opus 4.5) -> specialized Sub Agent delegation

Existing sql_agent.py and graph.py are preserved and reused.
The Orchestrator wraps them with intelligent routing.
"""

import json

import structlog
from langchain_anthropic import ChatAnthropic

from app.models.agent_models import AgentModel

# Existing agent (no modifications)
from app.agents.sql_agent import run_sql_agent

# v3.0 new agents
from app.agents.query_verifier import QueryVerifierAgent
from app.agents.notion_agent import NotionAgent
from app.agents.gws_agent import GWSAgent

logger = structlog.get_logger(__name__)


class OrchestratorAgent:
    """Orchestrator-Worker pattern conductor.

    Analyzes query intent and delegates to appropriate Sub Agent.
    """

    def __init__(self):
        # LLM for classification: use Anthropic if key is available, else None (keyword fallback)
        self.llm = None
        try:
            from app.config import get_settings
            settings = get_settings()
            if settings.anthropic_api_key and not settings.anthropic_api_key.startswith("your-"):
                self.llm = ChatAnthropic(
                    model=AgentModel.ORCHESTRATOR.value,
                    temperature=0,
                    max_tokens=1024,
                )
                logger.info("orchestrator_llm_ready", model=AgentModel.ORCHESTRATOR.value)
            else:
                logger.warning("orchestrator_no_anthropic_key", fallback="keyword_routing")
        except Exception as e:
            logger.warning("orchestrator_llm_init_failed", error=str(e), fallback="keyword_routing")

        # v3.0 new agents (lazy init — only created when actually needed)
        self._query_verifier = None
        self._notion_agent = None
        self._gws_agent = None

    @property
    def query_verifier(self):
        if self._query_verifier is None:
            self._query_verifier = QueryVerifierAgent()
        return self._query_verifier

    @property
    def notion_agent(self):
        if self._notion_agent is None:
            self._notion_agent = NotionAgent()
        return self._notion_agent

    @property
    def gws_agent(self):
        if self._gws_agent is None:
            self._gws_agent = GWSAgent()
        return self._gws_agent

    async def route_and_execute(self, query: str) -> dict:
        """Main entry point: analyze query -> delegate to Sub Agent -> return result.

        Args:
            query: User's natural language question.

        Returns:
            {"source": str, "answer": str, ...}
        """
        # Step 1: Classify query intent
        route = await self._classify_query(query)
        logger.info("orchestrator_routed", query=query[:100], route=route)

        # Step 2: Execute via Sub Agent
        handlers = {
            "bigquery": self._handle_bigquery,
            "notion": self._handle_notion,
            "gws": self._handle_gws,
            "multi": self._handle_multi,
        }
        handler = handlers.get(route, self._handle_direct)
        return await handler(query)

    async def _classify_query(self, query: str) -> str:
        """Orchestrator determines query type.

        Uses LLM classification if Anthropic key is available,
        otherwise falls back to keyword-based routing.
        """
        # Try LLM classification first
        if self.llm:
            try:
                prompt = f"""사용자 질문을 분석하여 적절한 처리 경로를 결정하세요.

경로 옵션:
- bigquery: 매출, 수량, 주문, 재고, 데이터 조회/분석/집계 관련
- notion: 사내 문서, 정책, 매뉴얼, 제품 정보, 프로세스 관련
- gws: Google Drive 파일, Gmail 메일, Calendar 일정 관련
- multi: 여러 소스가 필요한 복합 질문 (예: "매출 하락 원인 분석")
- direct: 일반 지식, 용어 설명, 간단한 질문

질문: {query}

경로 하나만 답변 (bigquery/notion/gws/multi/direct):"""

                response = await self.llm.ainvoke(prompt)
                route = response.content.strip().lower()

                valid_routes = {"bigquery", "notion", "gws", "multi", "direct"}
                if route in valid_routes:
                    return route
            except Exception as e:
                logger.warning("llm_classify_failed", error=str(e))

        # Keyword-based fallback
        return self._keyword_classify(query)

    def _keyword_classify(self, query: str) -> str:
        """Keyword-based query classification fallback."""
        q = query.lower()
        if any(kw in q for kw in [
            "매출", "수량", "주문", "sales", "revenue",
            "쇼피", "아마존", "틱톡", "국가별", "월별",
            "대륙별", "플랫폼별", "연도별", "분기별",
            "라인", "차트", "그래프", "그려",
        ]):
            return "bigquery"
        elif any(kw in q for kw in ["정책", "매뉴얼", "프로세스", "가이드", "반품"]):
            return "notion"
        elif any(kw in q for kw in ["드라이브", "메일", "캘린더", "회의록", "일정"]):
            return "gws"
        return "direct"

    async def _handle_bigquery(self, query: str) -> dict:
        """BigQuery Agent: reuses existing run_sql_agent().

        The existing sql_agent pipeline already handles:
        generate_sql -> validate_sql -> execute_sql -> format_answer (with chart)
        """
        try:
            answer = await run_sql_agent(query)
            return {"source": "bigquery", "answer": answer}
        except Exception as e:
            logger.error("orchestrator_bigquery_failed", error=str(e))
            return {"source": "bigquery", "error": str(e), "answer": f"데이터 조회 중 오류: {str(e)}"}

    async def _handle_notion(self, query: str) -> dict:
        """Notion Sub Agent execution."""
        result = await self.notion_agent.run(query)
        return {"source": "notion", "answer": result}

    async def _handle_gws(self, query: str) -> dict:
        """Google Workspace Sub Agent execution."""
        result = await self.gws_agent.run(query)
        return {"source": "gws", "answer": result}

    async def _handle_multi(self, query: str) -> dict:
        """Multi-source: run BigQuery + Notion in parallel, then synthesize."""
        results = {}

        # BigQuery
        try:
            bq_answer = await run_sql_agent(query)
            results["bigquery"] = {"answer": bq_answer}
        except Exception as e:
            results["bigquery"] = {"error": str(e)}

        # Notion
        try:
            notion_answer = await self.notion_agent.run(query)
            results["notion"] = {"answer": notion_answer}
        except Exception as e:
            results["notion"] = {"error": str(e)}

        # Synthesize with Orchestrator
        summary_prompt = f"""다음은 여러 소스에서 수집한 정보입니다.
이를 종합하여 사용자 질문에 답변하세요.

질문: {query}
수집 결과: {json.dumps(results, ensure_ascii=False, default=str)}

종합 답변:"""

        try:
            if self.llm:
                response = await self.llm.ainvoke(summary_prompt)
                answer = response.content
            else:
                from app.core.llm import get_gemini_client
                answer = get_gemini_client().generate(summary_prompt, temperature=0.3)
        except Exception as e:
            logger.warning("multi_synthesize_failed", error=str(e))
            answer = json.dumps(results, ensure_ascii=False, default=str)

        return {
            "source": "multi",
            "answer": answer,
            "sub_results": results,
        }

    async def _handle_direct(self, query: str) -> dict:
        """General question: direct LLM answer."""
        if self.llm:
            try:
                response = await self.llm.ainvoke(query)
                return {"source": "direct", "answer": response.content}
            except Exception as e:
                logger.warning("direct_llm_failed", error=str(e))

        # Fallback to Gemini
        from app.core.llm import get_gemini_client
        llm = get_gemini_client()
        answer = llm.generate(query, temperature=0.3)
        return {"source": "direct", "answer": answer}
