from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import (
    RAGFAQRequest,
    RAGFAQResponse,
    RAGAskAIRequest,
    RAGAskAIResponse,
    SafetyAlertResponse,
    EquipmentHealthResponse,
    A2RecommendRequest,
    A2RecommendResponse,
    DamageCriteriaResponse,
    ToolContentChunkResponse,
    ScenarioToolMatch,
)
from .auth import get_current_user, get_optional_user
from ..services.rag_local_service import (
    LocalKnowledgeBase,
    get_safety_alert,
    calculate_equipment_health,
)
from ..ai.gateway import AIGateway

router = APIRouter(prefix="/api/v1/rag", tags=["RAG & Knowledge (本地知識庫與指引)"])


@router.post(
    "/recommend",
    response_model=A2RecommendResponse,
    summary="A2 自然語言情境搜尋與標籤推薦 (AI Gateway)",
)
def recommend_scenario(
    req: A2RecommendRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    """
    透過後端代理之 Gemini API，將住戶修繕情境轉為標準工具標籤。
    - 具備 4 大降級保護 (逾時降級、無庫存引導、格式異常解析、非修繕親切拒答)。
    - 實作 24 小時語意快取與每分鐘 5 次 Rate Limit。
    """
    gateway = AIGateway.get_instance()
    user_id = current_user.id if current_user else 1001
    community_id = current_user.community_id if current_user else 1
    return gateway.recommend_scenario(
        user_id=user_id,
        prompt=req.prompt,
        db=db,
        community_id=community_id,
    )


@router.post("/faq", response_model=RAGFAQResponse, summary="U1 操作指引 FAQ 本地檢索")
def search_faq(req: RAGFAQRequest):
    """
    U1 操作指引 FAQ 本地關鍵字檢索。
    - 零外部 LLM 依賴，零 Token 成本，延遲 < 50ms。
    - 支援 5 大示範工具操作步驟檢索與吉祥物狸利降級親切引導。
    """
    kb = LocalKnowledgeBase.get_instance()
    return kb.search_faq(
        question=req.question,
        tool_name=req.tool_name,
        tool_id=req.tool_id,
    )


@router.post("/ask-ai", response_model=RAGAskAIResponse, summary="U1 知識庫 AI 智能問答 (RAG QA)")
def ask_ai_endpoint(
    req: RAGAskAIRequest,
    current_user: User | None = Depends(get_optional_user),
):
    """
    結合本地知識庫手冊 (RAG Context) 與 Gemini AI 生成精準操作指南與排除建議。
    - 即時檢索手冊條目作為 Context 注入給 Gemini。
    - 以吉祥物狸利工程師口吻親切解答，強調工安防護，嚴禁出現違規名詞。
    """
    kb = LocalKnowledgeBase.get_instance()
    res = kb.ask_ai_with_rag(
        question=req.question,
        tool_id=req.tool_id,
        tool_name=req.tool_name,
    )
    return RAGAskAIResponse(**res)


@router.get(
    "/damage-criteria/{tool_id}",
    response_model=DamageCriteriaResponse,
    summary="SPEC_04 Check-out 差分比對標準與賠付比例查詢",
)
def get_damage_criteria_endpoint(tool_id: str):
    """
    Check-out AI 影像比對標準依據 (SPEC_04)。
    - 提供 MINOR_DIFF (30%) 與 DAMAGE_DETECTED (100%) 之具體照片判別標準。
    - 明確標記功能性故障（如馬達、電池、燈泡、防水層）排除於照片比對範圍外，須走爭議協商。
    """
    kb = LocalKnowledgeBase.get_instance()
    criteria = kb.get_damage_criteria(tool_id)
    if not criteria:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"知識庫中查無工具代碼 '{tool_id}' 之損壞判定標準。",
        )
    return DamageCriteriaResponse(**criteria)


@router.get(
    "/tool-content/{tool_id}",
    response_model=List[ToolContentChunkResponse],
    summary="U1 操作與安全指引內容檢索",
)
def get_tool_content_endpoint(
    tool_id: str,
    query: Optional[str] = Query(None, description="過濾問題或關鍵字"),
    category: Optional[str] = Query(None, description="指定分類（操作手冊/安全警語/常見問題/規格/套裝內容）"),
    tool_name: Optional[str] = Query(None, description="工具品名輔助匹配"),
):
    """
    U1 取件後安全與操作指引端點。
    - 本地檢索，延遲 < 50ms，零外部 Token 成本。
    - 輸出含原廠說明手冊與實測心得之 source_ref 可信度分級標註。
    """
    kb = LocalKnowledgeBase.get_instance()
    results = kb.find_content_by_tool(tool_id, query=query, category=category)
    if not results and tool_name:
        results = kb.find_content_by_tool(tool_name, query=query, category=category)
    return [ToolContentChunkResponse(**r) for r in results]


@router.post(
    "/scenario-tools",
    response_model=List[ScenarioToolMatch],
    summary="A2 情境標籤對齊工具清單 (純本地檢索)",
)
def get_scenario_tools_endpoint(req: A2RecommendRequest):
    """
    A2 根據自然語言修繕情境，快速比對知識庫 category='使用情境標籤' 之 use_case_tags。
    """
    kb = LocalKnowledgeBase.get_instance()
    matches = kb.find_tool_by_scenario(req.prompt)
    return [
        ScenarioToolMatch(
            tool_id=m["tool_id"],
            tool_name=m["tool_name"],
            tool_category=m["tool_category"],
            matched_tags=m["matched_tags"],
            content_summary=m["content"],
            source_ref=m["source_ref"],
        )
        for m in matches
    ]


@router.get("/safety/{category}", response_model=SafetyAlertResponse, summary="UC-4 工具類別安全注意事項與護具提示")
def get_safety_for_category(category: str):
    """
    UC-4 出租與借用安全須知檢索。
    - 根據分類提供危險等級、防護裝備 (PPE)、操作防護規則與吉祥物狸利友善提醒。
    """
    return get_safety_alert(category)


@router.get("/safety-alert/{category}", response_model=SafetyAlertResponse, summary="UC-4 工具安全提醒別名端點")
def get_safety_alert_alias(category: str):
    return get_safety_alert(category)


@router.get("/equipment-health/{item_id}", response_model=EquipmentHealthResponse, summary="UC-5 裝備健康評級與摘要")
def get_equipment_health(item_id: int, db: Session = Depends(get_db)):
    """
    UC-5 裝備健康評級統計引擎。
    - 根據借出與損壞次數輸出等級 A / B / C 與保養建議。
    """
    return calculate_equipment_health(db, item_id)

