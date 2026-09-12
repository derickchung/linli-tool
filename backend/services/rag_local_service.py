import glob
import json
import os
import re
import math
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session

from ..models import Item, Order, OrderStatus, DisputeTicket
from ..schemas import (
    RAGFAQResponse,
    FAQMatch,
    SafetyAlertResponse,
    EquipmentHealthResponse,
)

TOOL_ID_MAP = {
    "TOOL_DRILL_01": "bosch-gsb185li-30pc",
    "DRILL-BOSCH-18V": "bosch-gsb185li-30pc",
    "BOSCH-GSB185LI-30PC": "bosch-gsb185li-30pc",
    "TOOL_LADDER_01": "generic-aframe-ladder-6step",
    "GENERIC-AFRAME-LADDER-6STEP": "generic-aframe-ladder-6step",
    "TOOL_WASHER_01": "karcher-k3-power-control",
    "KARCHER-K3-POWER-CONTROL": "karcher-k3-power-control",
    "TOOL_PROJECTOR_01": "jmgo-n1s-infinity-4k",
    "TOOL_LASER_01": "jmgo-n1s-infinity-4k",
    "JMGO-N1S-INFINITY-4K": "jmgo-n1s-infinity-4k",
    "TOOL_TENT_01": "snowpeak-landnest-tp259",
    "SNOWPEAK-LANDNEST-TP259": "snowpeak-landnest-tp259",
}


def resolve_tool_id(raw_id: Optional[str]) -> Optional[str]:
    if not raw_id:
        return None
    normalized = raw_id.strip().upper()
    if normalized in TOOL_ID_MAP:
        return TOOL_ID_MAP[normalized]
    for k, v in TOOL_ID_MAP.items():
        if k.lower() == raw_id.strip().lower() or v.lower() == raw_id.strip().lower():
            return v
    return raw_id.strip().lower()


@dataclass
class LocalFAQEntry:
    tool_id: str
    tool_name: str
    category: str
    question: str
    answer: str
    source_file: str
    keywords: List[str]


class LocalKnowledgeBase:
    _instance = None

    def __init__(self, kb_dir: Optional[str] = None):
        if kb_dir is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            kb_dir = os.path.abspath(os.path.join(current_dir, "..", "knowledge_base"))
        self.kb_dir = kb_dir
        self.entries: List[LocalFAQEntry] = []
        self.tool_meta: Dict[str, dict] = {}
        self.json_chunks: List[Dict[str, Any]] = []
        self.json_meta: Dict[str, Any] = {}
        self.chunks_by_tool: Dict[str, List[Dict[str, Any]]] = {}
        self.scenario_chunks: List[Dict[str, Any]] = []
        self.damage_criteria_by_tool: Dict[str, Dict[str, Any]] = {}
        self.df = Counter()
        self.num_entries = 0
        self.load_documents()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = LocalKnowledgeBase()
        return cls._instance

    def load_documents(self):
        self.entries.clear()
        self.tool_meta.clear()
        self.json_chunks.clear()
        self.chunks_by_tool.clear()
        self.scenario_chunks.clear()
        self.damage_criteria_by_tool.clear()

        # 1. Load Markdown files
        md_files = glob.glob(os.path.join(self.kb_dir, "*.md"))
        for file_path in md_files:
            filename = os.path.basename(file_path)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self._parse_markdown(filename, content)
            except Exception as e:
                print(f"[Warning] Failed to load KB document {file_path}: {e}")

        # 2. Load JSON Knowledge Base (v1.3.1 standard)
        json_path = os.path.join(self.kb_dir, "knowledge_base.json")
        if os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    kb_data = json.load(f)
                self._parse_json_knowledge_base(kb_data)
            except Exception as e:
                print(f"[Warning] Failed to load JSON Knowledge Base {json_path}: {e}")

        # Build Document Frequency (DF) map across all entries
        self.df = Counter()
        for entry in self.entries:
            seen_tokens = set(entry.keywords)
            for tok in seen_tokens:
                self.df[tok] += 1
        self.num_entries = len(self.entries)

    def _parse_json_knowledge_base(self, data: Dict[str, Any]):
        self.json_meta = data.get("knowledge_base_meta", {})
        chunks = data.get("chunks", [])
        self.json_chunks = chunks

        for chunk in chunks:
            raw_tool_id = chunk.get("tool_id", "")
            canonical_id = resolve_tool_id(raw_tool_id) or raw_tool_id
            category = chunk.get("category", "")
            tool_name = chunk.get("tool_name", "")
            content = chunk.get("content", "")

            # Index by tool_id
            if canonical_id not in self.chunks_by_tool:
                self.chunks_by_tool[canonical_id] = []
            self.chunks_by_tool[canonical_id].append(chunk)

            # Record in tool_meta if not already present
            if canonical_id not in self.tool_meta:
                self.tool_meta[canonical_id] = {
                    "tool_id": canonical_id,
                    "tool_name": tool_name,
                    "category": chunk.get("tool_category", "HAND_TOOLS"),
                    "filename": "knowledge_base.json",
                }

            # Scenario chunks (category == "使用情境標籤")
            if category == "使用情境標籤":
                self.scenario_chunks.append(chunk)

            # Damage criteria chunks (category == "損壞判定標準")
            elif category == "損壞判定標準":
                self.damage_criteria_by_tool[canonical_id] = chunk

            # FAQ / Manual chunks -> add to searchable FAQ entries
            if category == "常見問題":
                qa_matches = re.findall(r"Q[:：]\s*(.*?)\s*A[:：]\s*(.*?)(?=Q[:：]|$)", content, re.DOTALL)
                for q, a in qa_matches:
                    q_clean = q.strip()
                    a_clean = a.strip()
                    keywords = self._extract_tokens(f"{q_clean} {a_clean} {tool_name}")
                    self.entries.append(
                        LocalFAQEntry(
                            tool_id=canonical_id,
                            tool_name=tool_name,
                            category=chunk.get("tool_category", "HAND_TOOLS"),
                            question=q_clean,
                            answer=a_clean,
                            source_file=f"knowledge_base.json#{chunk.get('chunk_id')}",
                            keywords=keywords,
                        )
                    )
            elif category in ["操作手冊", "安全警語"]:
                summary_q = f"{tool_name} {category}重點指南"
                keywords = self._extract_tokens(f"{summary_q} {content} {tool_name}")
                self.entries.append(
                    LocalFAQEntry(
                        tool_id=canonical_id,
                        tool_name=tool_name,
                        category=chunk.get("tool_category", "HAND_TOOLS"),
                        question=summary_q,
                        answer=content,
                        source_file=f"knowledge_base.json#{chunk.get('chunk_id')}",
                        keywords=keywords,
                    )
                )

    def find_tool_by_scenario(self, scenario_text: str) -> List[Dict[str, Any]]:
        """
        A2 情境推薦查詢：比對 category="使用情境標籤" 底下的 use_case_tags 與 content
        輸入：自然語言情境描述（如「牆上想釘層板」、「浴室水垢清洗」、「露營搭帳」）
        輸出：候選工具清單 (tool_id, tool_name, tool_category, matched_tags, content, source_ref)
        """
        s_lower = scenario_text.lower()
        s_tokens = self._extract_tokens(scenario_text)
        matches = []

        for chunk in self.scenario_chunks:
            tags = chunk.get("use_case_tags", [])
            content = chunk.get("content", "")
            matched_tags = []

            for tag in tags:
                tag_lower = tag.lower()
                if tag_lower in s_lower or any(t in tag_lower for t in s_tokens if len(t) >= 2):
                    matched_tags.append(tag)

            content_hit = any(t in content for t in s_tokens if len(t) >= 2)

            if matched_tags or content_hit:
                matches.append({
                    "tool_id": resolve_tool_id(chunk.get("tool_id")) or chunk.get("tool_id"),
                    "tool_name": chunk.get("tool_name"),
                    "tool_category": chunk.get("tool_category"),
                    "matched_tags": matched_tags if matched_tags else tags[:3],
                    "content": content,
                    "source_ref": chunk.get("source_ref"),
                    "score": len(matched_tags) * 3 + (1 if content_hit else 0),
                })

        matches.sort(key=lambda x: x["score"], reverse=True)
        return matches

    def find_content_by_tool(
        self,
        tool_id: str,
        query: Optional[str] = None,
        category: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        U1 操作與安全指引查詢：以 tool_id 過濾 (支援操作手冊/安全警語/常見問題/規格/套裝內容)
        """
        canonical_id = resolve_tool_id(tool_id) or tool_id.strip().lower()
        chunks = self.chunks_by_tool.get(canonical_id, [])
        if not chunks:
            for tid, clist in self.chunks_by_tool.items():
                if tid in canonical_id or canonical_id in tid:
                    chunks = clist
                    break

        results = []
        q_lower = query.lower() if query else None
        q_tokens = self._extract_tokens(query) if query else []

        for c in chunks:
            c_cat = c.get("category", "")
            if category and c_cat != category:
                continue

            score = 1.0
            if q_lower:
                c_content = (c.get("content", "") + " " + c.get("tool_name", "")).lower()
                match_count = sum(1 for t in q_tokens if t in c_content)
                if match_count == 0 and len(q_tokens) > 0:
                    continue
                score += match_count

            results.append({
                "chunk_id": c.get("chunk_id"),
                "tool_id": canonical_id,
                "tool_name": c.get("tool_name"),
                "tool_category": c.get("tool_category"),
                "category": c_cat,
                "content": c.get("content"),
                "source_ref": c.get("source_ref"),
                "use_case_tags": c.get("use_case_tags"),
                "last_verified_at": c.get("last_verified_at"),
                "score": score,
            })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    def get_damage_criteria(self, tool_id: str) -> Optional[Dict[str, Any]]:
        """
        Check-out 影像比對損壞判定依據查詢 (SPEC_04)
        輸出 MINOR_DIFF (30%)、DAMAGE_DETECTED (100%) 依據，與功能性故障排除說明
        """
        canonical_id = resolve_tool_id(tool_id) or tool_id.strip().lower()
        chunk = self.damage_criteria_by_tool.get(canonical_id)

        if not chunk:
            for tid, c in self.damage_criteria_by_tool.items():
                if tid in canonical_id or canonical_id in tid:
                    chunk = c
                    canonical_id = tid
                    break

        if not chunk:
            return None

        content = chunk.get("content", "")

        minor_part = ""
        damage_part = ""
        excluded_part = ""

        m_minor = re.search(r"MINOR_DIFF[（\(]([^）\)]*)[）\)]\s*[:：]\s*([^。]+。)", content)
        if m_minor:
            minor_note = m_minor.group(1).strip()
            minor_text = m_minor.group(2).strip()
            minor_part = f"{minor_text}（{minor_note}）"
        else:
            minor_part = "外觀輕微表面刮痕磨損，主體核心結構完整（賠付比例 30%）。"

        m_damage = re.search(r"DAMAGE_DETECTED[（\(]([^）\)]*)[）\)]\s*[:：]\s*([^。]+。)", content)
        if m_damage:
            damage_note = m_damage.group(1).strip()
            damage_text = m_damage.group(2).strip()
            damage_part = f"{damage_text}（{damage_note}）"
        else:
            damage_part = "外殼破裂、配件缺失、結構變形或電線外露（賠付比例 100%）。"

        m_ex = re.search(r"範圍外[（\(][^）\)]*[）\)]\s*[:：]\s*(.*)", content)
        if m_ex:
            excluded_part = m_ex.group(1).strip()
        else:
            excluded_part = "馬達運轉、通電啟動、內部機件老化等功能性檢測非本AI相片比對機制覆蓋範圍，如有異常請走人工爭議協商。"

        return {
            "tool_id": canonical_id,
            "tool_name": chunk.get("tool_name"),
            "tool_category": chunk.get("tool_category"),
            "category": "損壞判定標準",
            "raw_content": content,
            "minor_diff_criteria": minor_part,
            "damage_detected_criteria": damage_part,
            "excluded_scope": excluded_part,
            "source_ref": chunk.get("source_ref"),
            "last_verified_at": chunk.get("last_verified_at"),
        }

    def _parse_markdown(self, filename: str, content: str):
        # Extract Tool ID
        tool_id_match = re.search(r"-\s*\*\*工具代碼\*\*：`?([A-Za-z0-9_]+)`?", content)
        tool_id = tool_id_match.group(1) if tool_id_match else filename.replace(".md", "")

        # Extract Tool Name
        tool_name_match = re.search(r"-\s*\*\*品名\*\*：([^\n]+)", content)
        tool_name = tool_name_match.group(1).strip() if tool_name_match else tool_id

        # Extract Category
        cat_match = re.search(r"-\s*\*\*分類\*\*：`?([A-Za-z0-9_]+)`?", content)
        category = cat_match.group(1).strip() if cat_match else "HAND_TOOLS"

        self.tool_meta[tool_id] = {
            "tool_id": tool_id,
            "tool_name": tool_name,
            "category": category,
            "filename": filename,
        }

        # Parse Q&A pairs
        qa_sections = re.split(r"\n###\s+Q\d*:\s*", content)
        for section in qa_sections[1:]:
            parts = section.split("\n", 1)
            q_line = parts[0].strip()
            rest = parts[1] if len(parts) > 1 else ""

            ans_clean = rest.strip()
            if "**步驟解答**：" in ans_clean:
                ans_clean = ans_clean.split("**步驟解答**：", 1)[1].strip()

            if "\n## " in ans_clean:
                ans_clean = ans_clean.split("\n## ", 1)[0].strip()

            keywords = self._extract_tokens(f"{q_line} {ans_clean} {tool_name}")
            self.entries.append(
                LocalFAQEntry(
                    tool_id=tool_id,
                    tool_name=tool_name,
                    category=category,
                    question=q_line,
                    answer=ans_clean,
                    source_file=f"knowledge_base/{filename}",
                    keywords=keywords,
                )
            )


    def _extract_tokens(self, text: str) -> List[str]:
        cleaned = re.sub(r"[^\w\s\u4e00-\u9fff]", " ", text.lower())
        tokens = cleaned.split()
        # Also add 2-character n-grams for Chinese terms
        c_tokens = []
        for t in tokens:
            if re.search(r"[\u4e00-\u9fff]", t) and len(t) >= 2:
                for i in range(len(t) - 1):
                    c_tokens.append(t[i : i + 2])
        return list(set(tokens + c_tokens))

    def search_faq(
        self,
        question: str,
        tool_name: Optional[str] = None,
        tool_id: Optional[str] = None,
    ) -> RAGFAQResponse:
        q_tokens = self._extract_tokens(question)
        if not q_tokens:
            return RAGFAQResponse(
                answer="我是鄰里工具工程師狸利，請問您有什麼想查詢的操作步驟呢？",
                source="knowledge_base/fallback",
                confidence=0.0,
                matched_tool_id=None,
                related_qas=[],
            )

        best_score = 0.0
        best_entry: Optional[LocalFAQEntry] = None
        scored_matches: List[tuple] = []
        N = max(1, len(self.entries))

        for entry in self.entries:
            # Score based on TF-IDF
            score = 0.0
            for qt in q_tokens:
                doc_freq = self.df.get(qt, 1)
                # IDF weighting: rare keywords get much higher weight than common words like "如何", "安全"
                idf = math.log((N + 1.0) / (doc_freq + 1.0)) + 1.0

                if qt in entry.question.lower():
                    score += idf * 4.0
                elif any(qt in k for k in entry.keywords):
                    score += idf * 1.0

            # Boost if tool matches
            if tool_id and entry.tool_id.upper() == tool_id.upper():
                score *= 2.0
            elif tool_name and (tool_name.lower() in entry.tool_name.lower() or entry.tool_name.lower() in tool_name.lower()):
                score *= 1.5

            if score > 0:
                scored_matches.append((score, entry))
                if score > best_score:
                    best_score = score
                    best_entry = entry

        scored_matches.sort(key=lambda x: x[0], reverse=True)

        normalized_best_score = min(1.0, best_score / (len(q_tokens) * 12.0)) if best_entry else 0.0

        if not best_entry or normalized_best_score < 0.20:
            return RAGFAQResponse(
                answer=(
                    f"我是鄰里工具工程師狸利，暫時沒有找到關於「{question}」的直接操作指引。"
                    "建議先參閱工具機身上的安全標籤，或直接在社區內洽詢出借鄰居喔！"
                ),
                source="knowledge_base/fallback",
                confidence=0.0,
                matched_tool_id=tool_id,
                related_qas=[],
            )

        related = [
            FAQMatch(
                question=m[1].question,
                answer=m[1].answer[:120] + "..." if len(m[1].answer) > 120 else m[1].answer,
                tool_id=m[1].tool_id,
                score=round(min(1.0, m[0] / (len(q_tokens) * 12.0)), 2),
            )
            for m in scored_matches[1:4]
        ]

        return RAGFAQResponse(
            answer=best_entry.answer,
            source=best_entry.source_file,
            confidence=round(normalized_best_score, 2),
            matched_tool_id=best_entry.tool_id,
            related_qas=related,
        )


# ==============================
# UC-4 Safety Alerts Table
# ==============================

SAFETY_TABLE = {
    "POWER_TOOLS": {
        "risk_level": "HIGH",
        "required_ppe": ["防護眼鏡 (護目鏡)", "防塵口罩", "工作防滑手套", "防噪音耳塞"],
        "precautions": [
            "操作時請雙手握持機身與把手，身體保持平衡，切勿單手操作以防扭力反扭。",
            "在牆壁或地面鑽孔前，請務必先確認暗埋管線位置（電線、水管、瓦斯管）。",
            "更換鑽頭或起子配件前，必須先拔除電池或切換至安全鎖定檔。",
            "嚴禁在潮濕或積水環境操作動力工具。",
        ],
        "microcopy_tip": "狸利提醒您：安全第一！動力工具轉速扭力大，操作前請確實穿戴防護眼鏡與手套喔！",
    },
    "CLEANING": {
        "risk_level": "MEDIUM",
        "required_ppe": ["護目鏡", "防滑防水長靴", "橡膠防護手套"],
        "precautions": [
            "高壓水柱衝擊力強，嚴禁將噴槍對準人體、寵物、眼睛或脆弱表面。",
            "使用高壓清洗機前，務必先開水龍頭並扣板機排空空氣，出水順暢後方可開機。",
            "乾濕兩用吸塵器吸水前，務必拆下乾式 HEPA 濾心，改裝防水海綿濾套。",
            "電源插座與延長線請保持高於地面，嚴禁浸泡於積水中。",
        ],
        "microcopy_tip": "狸利提醒您：高壓水柱與吸水設備請注意電器防護與防滑穿著喔！",
    },
    "CAMPING": {
        "risk_level": "LOW",
        "required_ppe": ["耐熱手套", "防風防雨外套"],
        "precautions": [
            "瓦斯爐具與炭火嚴禁在密閉帳篷內使用，務必保持通風以防一氧化碳中毒。",
            "營釘請務必以 45 度角打入地面至貼平，避免孩童行走絆倒受傷。",
            "歸還前請務必將裝備完全曬乾並清除泥砂，預防帳篷受潮發霉發臭。",
        ],
        "microcopy_tip": "狸利提醒您：露營裝備乾收是美德，營火與卡式爐務必注意通風防火安全喔！",
    },
    "GARDENING": {
        "risk_level": "MEDIUM",
        "required_ppe": ["防刺厚手套", "護目鏡", "長袖長褲"],
        "precautions": [
            "修剪高處樹枝請先確認落枝範圍無人，並配戴安全帽與護目鏡防木屑落眼。",
            "使用修草機或綠籬機請留意地面石塊，防碎石高速飛濺傷人。",
            "手動園藝剪刀使用完畢請立即合上安全鎖扣，避免誤觸劃傷。",
        ],
        "microcopy_tip": "狸利提醒您：園藝修剪請注意碎屑飛濺與防刺防刮，保持周遭淨空喔！",
    },
    "HAND_TOOLS": {
        "risk_level": "LOW",
        "required_ppe": ["基本防滑工作手套", "平底防滑鞋 (登高時)"],
        "precautions": [
            "伸縮鋁梯展開時，務必親眼確認每階卡榫完全彈出鎖定，嚴禁兩人同時攀登。",
            "直梯靠牆請遵守 4:1 傾角法則（約 75 度），最高兩階切勿站立。",
            "雷射水平儀嚴禁直視光束或照射他人眼睛，搬運前請務必切至 LOCK 鎖定擺錘。",
            "螺絲起子與扳手請選用適配規格，避免螺絲滑牙損壞。",
        ],
        "microcopy_tip": "狸利提醒您：手動工具雖靈巧，操作伸縮梯或雷射儀器仍請遵守鎖定安全規則喔！",
    },
}


def get_safety_alert(category: str) -> SafetyAlertResponse:
    cat_upper = category.upper()
    data = SAFETY_TABLE.get(cat_upper, SAFETY_TABLE["HAND_TOOLS"])
    return SafetyAlertResponse(
        category=cat_upper,
        risk_level=data["risk_level"],
        required_ppe=data["required_ppe"],
        precautions=data["precautions"],
        microcopy_tip=data["microcopy_tip"],
    )


# ==============================
# UC-5 Equipment Health Rule Engine
# ==============================

def calculate_equipment_health(db: Session, item_id: int) -> EquipmentHealthResponse:
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"找不到編號為 {item_id} 的工具項目。",
        )

    # 1. 歷史總完成借用次數
    total_rentals = (
        db.query(Order)
        .filter(Order.item_id == item_id, Order.status == OrderStatus.COMPLETED)
        .count()
    )

    # 2. 歷史損壞回報次數 (vision_result != 'MATCH' 且不為 None)
    damage_count = (
        db.query(Order)
        .filter(
            Order.item_id == item_id,
            Order.vision_result.isnot(None),
            Order.vision_result != "MATCH",
        )
        .count()
    )

    # 3. 計算損壞率
    damage_rate = damage_count / max(1, total_rentals)

    # 4. 評級判定
    if total_rentals < 3 or damage_count == 0:
        health_grade = "A"
        summary = f"這項工具累計完成借出 {total_rentals} 次，狀況極佳，近期無結構損壞紀錄。"
        advice = "目前裝備狀況良好，建議每借出 15 次進行基本清潔與電量/零件常規保養。"
    elif damage_rate <= 0.15:
        health_grade = "B"
        summary = f"這項工具累計完成借出 {total_rentals} 次，損壞比率為 {damage_rate * 100:.1f}%，狀況良好，有些許正常使用痕跡。"
        advice = "裝備運作正常，交接時請確認主要配件是否齊全，並檢視外觀磨損狀況。"
    else:
        health_grade = "C"
        summary = f"這項工具累計完成借出 {total_rentals} 次，損壞或異常比率達 {damage_rate * 100:.1f}%，請注意曾有維修或損壞紀錄。"
        advice = "交接時請務必使用 Ghost Overlay 鏡頭仔細核對現有舊傷痕跡與配件清單，維護雙方借用權益。"

    return EquipmentHealthResponse(
        item_id=item.id,
        item_name=item.name,
        health_grade=health_grade,
        total_rentals=total_rentals,
        damage_count=damage_count,
        damage_rate=round(damage_rate, 3),
        summary=summary,
        maintenance_advice=advice,
    )
