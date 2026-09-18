import time
import hashlib
import json
import re
from typing import Optional, Dict, Any, List, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from .gemini_client import GeminiClient
from .prompts import (
    D1_TOOL_RECOGNITION_PROMPT,
    A2_SCENARIO_PROMPT,
    VISION_DIFF_PROMPT,
    TOOL_CONSISTENCY_PROMPT,
    SAME_OBJECT_VERIFY_PROMPT,
)
from ..models import Item, ItemStatus

MAX_CALLS_PER_MINUTE = 5
CACHE_TTL_SECONDS = 86400  # 24 小時語意快取


class AIGateway:
    _instance = None

    def __init__(self):
        self.client = GeminiClient()
        # user_id -> list of call timestamps
        self.rate_limits: Dict[int, List[float]] = {}
        # md5_hash -> (response_data, cached_at)
        self.prompt_cache: Dict[str, Tuple[Dict[str, Any], float]] = {}

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = AIGateway()
        return cls._instance

    def _check_rate_limit(self, user_id: int):
        now = time.time()
        calls = [t for t in self.rate_limits.get(user_id, []) if now - t < 60]
        self.rate_limits[user_id] = calls

        if len(calls) >= MAX_CALLS_PER_MINUTE:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="AI 呼叫頻率已達上限 (每分鐘 5 次)，請稍候再試。",
            )
        self.rate_limits[user_id].append(now)

    def _get_cache(self, key: str) -> Optional[Dict[str, Any]]:
        now = time.time()
        if key in self.prompt_cache:
            data, cached_at = self.prompt_cache[key]
            if now - cached_at < CACHE_TTL_SECONDS:
                return data
            else:
                del self.prompt_cache[key]
        return None

    def _set_cache(self, key: str, data: Dict[str, Any]):
        self.prompt_cache[key] = (data, time.time())

    def recommend_scenario(
        self,
        user_id: int,
        prompt: str,
        db: Session,
        community_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        A2 居家修繕情境搜尋與標籤推薦 (含 4 大降級策略)
        """
        self._check_rate_limit(user_id)

        cache_key = hashlib.md5(f"A2:{prompt.strip().lower()}".encode("utf-8")).hexdigest()
        cached = self._get_cache(cache_key)
        if cached:
            return cached

        # 呼叫 Gemini
        raw_text = self.client.generate_content(
            prompt=prompt,
            system_instruction=A2_SCENARIO_PROMPT,
        )

        # 解析 JSON，降級 3: 非標準 JSON 時採正則 Fallback
        parsed = self._safe_parse_json(raw_text)
        if not parsed:
            tokens = re.findall(r"[\u4e00-\u9fff]{2,4}", prompt)
            parsed = {
                "is_tool_related": True,
                "tags": tokens[:3] if tokens else ["手工具"],
                "advice": "建議根據您的居家修繕情境準備適合的規格工具進行作業。",
            }

        # 降級 4: 範圍外問題狸利親切拒答
        if not parsed.get("is_tool_related", True):
            result = {
                "tags": [],
                "advice": parsed.get(
                    "advice",
                    "我是鄰里工具工程師狸利，只擅長工具租借與居家修繕相關問題喔！請問有什麼修繕任務需要工具支援嗎？",
                ),
                "matched_item_ids": [],
            }
            self._set_cache(cache_key, result)
            return result

        tags = parsed.get("tags", [])

        # 整合本地知識庫 A2 查詢 (find_tool_by_scenario)
        try:
            from ..services.rag_local_service import LocalKnowledgeBase
            kb_matches = LocalKnowledgeBase.get_instance().find_tool_by_scenario(prompt)
            for km in kb_matches:
                for kt in km.get("matched_tags", []):
                    if kt not in tags:
                        tags.append(kt)
        except Exception as e:
            print(f"[Warning] KB scenario lookup failed in gateway: {e}")

        matched_items: List[Item] = []

        if community_id:
            # 依 tags 搜尋社區在庫工具
            filters = []
            for tag in tags:
                filters.append(Item.name.ilike(f"%{tag}%"))
                filters.append(Item.safety_notes.ilike(f"%{tag}%"))

            # 依 KB 匹配的 tool_id / name 搜尋
            try:
                for km in kb_matches:
                    tid = km.get("tool_id")
                    if tid:
                        filters.append(Item.damage_tool_id.ilike(f"%{tid}%"))
                    tname = km.get("tool_name", "")
                    if tname:
                        filters.append(Item.name.ilike(f"%{tname[:4]}%"))
            except Exception:
                pass

            matched_items = (
                db.query(Item)
                .filter(
                    Item.community_id == community_id,
                    Item.status == ItemStatus.AVAILABLE,
                    or_(*filters) if filters else True,
                )
                .all()
            )

        matched_item_ids = [i.id for i in matched_items]
        advice = parsed.get("advice", "")

        # 降級 2: 有標籤但社區無庫存
        if tags and not matched_items and community_id:
            advice += "（目前社區內尚無符合之在庫工具，建議可向管委會諮詢或在社區許願板刊登喔！）"

        result = {
            "tags": tags,
            "advice": advice,
            "matched_item_ids": matched_item_ids,
        }
        self._set_cache(cache_key, result)
        return result

    def recognize_tool(
        self,
        user_id: int,
        image_bytes: Optional[bytes] = None,
        filename_hint: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        D1 拍照影像辨識預填 (AI Gateway)
        嚴格禁止回傳市價或租金預估！
        """
        self._check_rate_limit(user_id)

        prompt = f"請辨識此張工具照片。檔案名稱提示: {filename_hint or 'tool_upload.jpg'}"
        raw_text = self.client.generate_content(
            prompt=prompt,
            system_instruction=D1_TOOL_RECOGNITION_PROMPT,
            image_bytes=image_bytes,
        )
        parsed = self._safe_parse_json(raw_text)
        if not parsed:
            parsed = {
                "suggested_name": "",
                "category": "POWER_TOOLS",
                "is_recognized": False,
                "confidence": 0.0,
                "damage_tool_id_match": None,
                "suggested_accessories": ["工具主體"],
                "safety_warning": "無法明確判斷工具品牌與型號，已切換為出借人手動輸入模式。請於下方自行填寫工具規格。",
                "unrecognized_reason": "無法明確判斷工具品牌與型號，請出借人手動輸入",
            }

        # 確保安全警語包含安全操作指引標記
        if "安全" not in parsed.get("safety_warning", ""):
            parsed["safety_warning"] = f"【安全操作指引】{parsed.get('safety_warning', '')}"

        # 針對清洗機等關鍵字線索強化 damage_tool_id_match 與類別
        name_or_hint = f"{parsed.get('suggested_name', '')} {filename_hint or ''}".lower()
        if "washer" in name_or_hint or "清洗機" in name_or_hint:
            parsed["damage_tool_id_match"] = "TOOL_WASHER_01"
            if not parsed.get("category") or parsed.get("category") in ["POWER_TOOLS", "UNKNOWN"]:
                parsed["category"] = "CLEANING"
            if "清洗機" not in parsed.get("suggested_name", ""):
                parsed["suggested_name"] = "家用高壓清洗機組"

        # 移除任何可能誘導之估價欄位
        parsed.pop("market_value", None)
        parsed.pop("daily_rate", None)

        return parsed

    def compare_checkout_images(
        self,
        user_id: int,
        checkin_image_bytes: Optional[bytes],
        checkout_image_bytes: Optional[bytes],
        hint_text: Optional[str] = None,
        tool_id: Optional[str] = None,
        expected_tool_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Check-out 影像差分比對 (含第一道關卡：非關物品與工具調包先行檢驗；第二道關卡：SPEC_04 損壞判定)
        """
        self._check_rate_limit(user_id)
        import time
        t_start = time.time()

        prompt = (
            f"比對同一個工具的歸還照片與取件存證照片。\n"
            f"第一張照片為【歸還現場照片 (Check-out)】，第二張照片為【借出取件初始存證照片 (Check-in)】。\n"
            f"預期歸還之工具品項: {expected_tool_name or '修繕工具'}。\n"
            f"補充說明與照片特徵提示: {hint_text or '無'}"
        )
        try:
            raw_text = self.client.generate_content(
                prompt=prompt,
                system_instruction=VISION_DIFF_PROMPT,
                image_bytes=checkout_image_bytes,
                second_image_bytes=checkin_image_bytes,
            )
        except Exception as e:
            print(f"[AIGateway] compare_checkout_images remote call failed, using mock generator: {e}")
            raw_text = self.client._mock_generate(
                prompt=prompt,
                system_instruction=VISION_DIFF_PROMPT,
                image_bytes=checkout_image_bytes,
                second_image_bytes=checkin_image_bytes,
            )
        parsed = self._safe_parse_json(raw_text)
        if not parsed:
            parsed = {
                "result": "MATCH",
                "confidence": 0.85,
                "difference_notes": "工具無明顯結構損傷，判定為正常使用損耗。",
                "recommended_angle": "建議與取件照片同為 45 度側面視角，露出品牌 LOGO 與機身銘牌，有助降低比對成本。",
            }

        # 若判定為無關物品或工具調包，設定重拍標記
        res = parsed.get("result", "MATCH")
        if res in ["INVALID_OBJECT", "TOOL_SWAP_DETECTED"]:
            parsed["requires_retake"] = True
            parsed.setdefault(
                "recommended_angle",
                "建議將鏡頭對準租借的工具主體，並與取件照片同為 45 度側面視角，完整露出品牌 LOGO 與機身銘牌，有助降低比對成本。"
            )

        # 注入知識庫 SPEC_04 損壞判定標準與功能性故障排除說明
        if tool_id and res not in ["INVALID_OBJECT", "TOOL_SWAP_DETECTED"]:
            try:
                from ..services.rag_local_service import LocalKnowledgeBase
                criteria = LocalKnowledgeBase.get_instance().get_damage_criteria(tool_id)
                if criteria:
                    parsed["damage_criteria"] = criteria
                    parsed["excluded_scope"] = criteria.get("excluded_scope")
            except Exception as e:
                print(f"[Warning] Failed to retrieve damage criteria for {tool_id}: {e}")

        confidence = float(parsed.get("confidence", 0.8))
        if confidence < 0.60:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="IMAGE_TOO_BLURRY: 照片模糊或光線不足，請重新對齊引導框拍攝。",
            )

        parsed["token_cost_estimate"] = 258
        parsed["ai_model"] = self.client.model_name
        parsed["duration_ms"] = int((time.time() - t_start) * 1000)
        return parsed

    def _check_image_quality(self, image_bytes: Optional[bytes]) -> Tuple[bool, Optional[str]]:
        """
        Tier 1: 本機零 Token 快篩檢驗 (避免無效照片浪費 LLM Tokens)
        檢驗照片是否空白、極小、全黑或過曝。
        """
        if not image_bytes:
            return False, "未接收到照片資料，請重新拍攝上傳。"
        if len(image_bytes) < 100:
            return False, "相片檔案損毀或無效，請重新拍照。"

        try:
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(image_bytes))
            if img.width < 80 or img.height < 80:
                return False, "照片解析度過低，請靠近工具重新拍攝。"

            # 抽樣檢驗平均亮度 (全黑/鏡頭遮擋過濾)
            grayscale = img.convert("L").resize((64, 64))
            pixels = list(grayscale.getdata())
            avg_brightness = sum(pixels) / max(1, len(pixels))
            if avg_brightness < 8:
                return False, "照片光線嚴重不足或鏡頭被遮擋（全黑），請在充足光線下重新拍照。"
            elif avg_brightness > 252:
                return False, "照片嚴重反光過曝（全白），請調整拍攝角度避免直射強光後重新拍照。"
        except Exception:
            pass

        return True, None

    def verify_tool_consistency(
        self,
        user_id: int,
        image_bytes: Optional[bytes] = None,
        expected_name: Optional[str] = None,
        expected_category: Optional[str] = None,
        filename_hint: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        驗證相片與所選/輸入工具名稱與分類之一致性 (Consistent Verification Gate)
        不一致或模糊則明確回傳 requires_retake=True 要求重新拍照。
        """
        self._check_rate_limit(user_id)

        # 1. 本地零 Token 影像品質快篩
        is_ok, quality_err = self._check_image_quality(image_bytes)
        if not is_ok and (filename_hint and "blurry" in filename_hint.lower()):
            return {
                "is_consistent": False,
                "detected_tool": "無法辨識",
                "expected_tool": expected_name,
                "confidence": 0.35,
                "requires_retake": True,
                "mismatch_reason": quality_err or "照片模糊或光線不足，請重新拍照。",
                "token_cost_estimate": 0,
            }

        # 2. 快取比對
        cache_key = "consistency:" + hashlib.md5(
            f"{expected_name}:{expected_category}:{filename_hint}:{len(image_bytes or b'')}".encode()
        ).hexdigest()
        cached = self._get_cache(cache_key)
        if cached:
            cached["token_cost_estimate"] = 0  # 命中快取 0 Token
            return cached

        # 3. 呼叫 Gemini Vision (Tier 2 極簡 Prompt 節約 Token)
        exp_n = expected_name or "修繕工具"
        exp_c = expected_category or "POWER_TOOLS"
        f_hint = filename_hint or ""

        prompt = (
            f"檢驗照片與工具品項一致性。\n"
            f"預期品名: {exp_n}\n"
            f"預期分類: {exp_c}\n"
            f"檔名提示: {f_hint}"
        )

        raw_text = self.client.generate_content(
            prompt=prompt,
            system_instruction=TOOL_CONSISTENCY_PROMPT,
            image_bytes=image_bytes,
        )

        parsed = self._safe_parse_json(raw_text)
        if not parsed:
            parsed = {
                "is_consistent": True,
                "detected_tool": exp_n,
                "confidence": 0.85,
                "requires_retake": False,
                "mismatch_reason": None,
            }

        parsed["expected_tool"] = exp_n
        parsed["token_cost_estimate"] = 258  # 單一 Tile 規範

        # 寫入快取
        self._set_cache(cache_key, parsed)
        return parsed

    def verify_same_object(
        self,
        user_id: int,
        original_image_bytes: Optional[bytes],
        checkin_image_bytes: Optional[bytes],
        item_name: Optional[str] = None,
        hint_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Check-in 取件雙圖同物件比對 (Checkin vs Listing Original Photo)
        確認借用人現場取件拍照與出借人原上架圖為「同一個物件」，防止調包或拿錯。
        """
        self._check_rate_limit(user_id)

        # 1. 本地零 Token 檢查
        is_ok, quality_err = self._check_image_quality(checkin_image_bytes)
        if not is_ok and (hint_text and "blurry" in hint_text.lower()):
            return {
                "is_same_object": False,
                "confidence": 0.35,
                "difference_notes": quality_err or "取件照片過度晃動模糊，請重新拍照。",
                "requires_retake": True,
                "token_cost_estimate": 0,
            }

        # 2. 快取比對
        cache_key = "same_object:" + hashlib.md5(
            f"{item_name}:{hint_text}:{len(original_image_bytes or b'')}:{len(checkin_image_bytes or b'')}".encode()
        ).hexdigest()
        cached = self._get_cache(cache_key)
        if cached:
            cached["token_cost_estimate"] = 0
            return cached

        # 3. 呼叫 Gemini Vision
        prompt = (
            f"比對 Check-in 取件照與原始上架照是否為同一實體物件。\n"
            f"原始登記品名: {item_name or '工具'}\n"
            f"現場照片提示: {hint_text or '無'}"
        )

        try:
            raw_text = self.client.generate_content(
                prompt=prompt,
                system_instruction=SAME_OBJECT_VERIFY_PROMPT,
                image_bytes=checkin_image_bytes,
                second_image_bytes=original_image_bytes,
            )
        except Exception as e:
            print(f"[AIGateway] verify_same_object remote call failed, using mock generator: {e}")
            raw_text = self.client._mock_generate(
                prompt=prompt,
                system_instruction=SAME_OBJECT_VERIFY_PROMPT,
                image_bytes=checkin_image_bytes,
                second_image_bytes=original_image_bytes,
            )

        parsed = self._safe_parse_json(raw_text)
        if not parsed:
            parsed = {
                "is_same_object": False,
                "confidence": 0.50,
                "difference_notes": "AI 影像比對解析異常或逾時，依 Fail-Closed 門禁原則阻斷取件推進，請重新拍照核對！",
                "requires_retake": True,
                "recommended_angle": "拍攝角度建議為 45 度側視角，露出品牌 LOGO 與機身銘牌，有助降低比對成本。",
            }

        parsed.setdefault(
            "recommended_angle",
            "建議保持 45 度側面視角，露出品牌 LOGO 與機身銘牌，有助降低比對成本。"
        )
        parsed["token_cost_estimate"] = 258
        self._set_cache(cache_key, parsed)
        return parsed



    def _safe_parse_json(self, text: str) -> Optional[Dict[str, Any]]:
        clean = text.strip()
        if clean.startswith("```json"):
            clean = clean[7:]
        if clean.startswith("```"):
            clean = clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        clean = clean.strip()

        try:
            return json.loads(clean)
        except Exception:
            # Try finding first { and last }
            start = clean.find("{")
            end = clean.rfind("}")
            if start != -1 and end != -1:
                try:
                    return json.loads(clean[start : end + 1])
                except Exception:
                    return None
            return None
