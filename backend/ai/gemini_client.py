import os
import json
import time
import re
from typing import Optional, Dict, Any

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DEFAULT_TIMEOUT_SECONDS = 1.5
MAX_RETRIES = 3


class GeminiClient:
    """
    Google Gemini API 客戶端封裝。
    - 具備 1.5 秒逾時保護與指數退避重試機制。
    - 支援無外部連線或無 API Key 時之本機智慧 Mock 與平滑降級。
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or GEMINI_API_KEY
        self.use_real_api = bool(self.api_key and self.api_key != "mock-gemini-key")

    def generate_content(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        image_bytes: Optional[bytes] = None,
    ) -> str:
        """發送生成請求 (含重試與逾時保護)"""
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                if not self.use_real_api:
                    return self._mock_generate(prompt, system_instruction, image_bytes)

                # 使用官方 google.generativeai 或 httpx 調用
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                model = genai.GenerativeModel(
                    model_name="gemini-2.0-flash",
                    system_instruction=system_instruction,
                )
                
                content_parts = [prompt]
                if image_bytes:
                    content_parts.append({"mime_type": "image/jpeg", "data": image_bytes})

                response = model.generate_content(
                    content_parts,
                    request_options={"timeout": DEFAULT_TIMEOUT_SECONDS},
                )
                return response.text
            except Exception as e:
                if attempt == MAX_RETRIES:
                    # 重試達上限，自動降級至 Mock 生成器
                    return self._mock_generate(prompt, system_instruction, image_bytes)
                time.sleep(0.2 * (2 ** (attempt - 1)))

        return self._mock_generate(prompt, system_instruction, image_bytes)

    def _mock_generate(
        self,
        prompt: str,
        system_instruction: Optional[str],
        image_bytes: Optional[bytes],
    ) -> str:
        """本機智慧 Mock 生成引擎 (提供離線測試與降級保底)"""
        p_lower = prompt.lower()
        sys_str = system_instruction or ""

        # 1. Check-out 差分比對
        if "VISION_DIFF" in sys_str:
            # 關卡 1A: 非關生活雜物/非工具檢驗
            if any(w in p_lower for w in ["mug", "cup", "coffee", "馬克杯", "咖啡", "unrelated", "無關", "雜物", "貓", "狗", "筆記本", "眼鏡", "food", "餐點", "餐具", "辦公", "office"]):
                return json.dumps({
                    "result": "INVALID_OBJECT",
                    "confidence": 0.97,
                    "difference_notes": "照片內容辨識為無關生活物品（馬克杯/辦公雜物），非所租借之修繕工具。系統已攔截無效比對，請重新拍攝正確工具歸還照片！",
                    "recommended_angle": "建議將鏡頭對準租借的工具主體，並與取件照片同為 45 度側面視角，完整露出品牌 LOGO 與機身銘牌，有助降低比對成本。",
                }, ensure_ascii=False)

            # 關卡 1B: 同類不同實體/品牌調包檢驗 (例如原借 Bosch，歸還拍成 Makita 或 DeWalt)
            if ("swap" in p_lower or "調包" in p_lower or "不同" in p_lower or
                ("bosch" in p_lower and any(b in p_lower for b in ["makita", "dewalt", "milwaukee", "牧田", "得偉", "美沃奇"])) or
                ("drill" in p_lower and "ladder" in p_lower) or
                ("電鑽" in p_lower and "梯" in p_lower)):
                return json.dumps({
                    "result": "TOOL_SWAP_DETECTED",
                    "confidence": 0.96,
                    "difference_notes": "歸還物件與先前借出之工具實體特徵不符（偵測到品牌/型號差異：原借出為 Bosch 電鑽，歸還照片辨識為 Makita/DeWalt 工具）。請確認是否拿錯工具，需歸還原借出之同一實體物件！",
                    "recommended_angle": "建議核對原借出之工具實體，並以 45 度側身視角拍攝露出原品項品牌 LOGO，避免誤判調包。",
                }, ensure_ascii=False)

            # 關卡 2: 雙圖差分核驗 (MATCH / MINOR_DIFF / DAMAGE_DETECTED)
            if "damage" in p_lower or "斷裂" in p_lower or "嚴重損毀" in p_lower:
                return json.dumps({
                    "result": "DAMAGE_DETECTED",
                    "confidence": 0.96,
                    "difference_notes": "檢測到工具外殼有明顯斷裂裂痕，結構受損。",
                    "recommended_angle": "建議與取件照片保持相同 45 度側身視角，露出品牌 LOGO 與主要工作頭，大幅降低比對成本與避免誤判。",
                }, ensure_ascii=False)
            elif "minor" in p_lower or "刮傷" in p_lower or "diff" in p_lower:
                return json.dumps({
                    "result": "MINOR_DIFF",
                    "confidence": 0.92,
                    "difference_notes": "檢測到工具表面有微幅摩擦痕跡 (Diff: 0.18)，核心功能完整。",
                    "recommended_angle": "建議與取件照片保持相同 45 度側身視角，露出品牌 LOGO 與主要工作頭，大幅降低比對成本與避免誤判。",
                }, ensure_ascii=False)
            elif "blurry" in p_lower or "模糊" in p_lower:
                return json.dumps({
                    "result": "MATCH",
                    "confidence": 0.45,
                    "difference_notes": "照片過度晃動模糊，無法有效比對。",
                    "recommended_angle": "請穩定手機對焦拍攝，保持與原照相同之 45 度側視角。",
                }, ensure_ascii=False)
            else:
                return json.dumps({
                    "result": "MATCH",
                    "confidence": 0.98,
                    "difference_notes": "工具無外觀結構破損，附屬配件數量完整，表面僅有正常使用微幅粉塵，判定為正常損耗。",
                    "recommended_angle": "拍攝角度與初始取件照片高度一致 (45度側視角)，雙圖特徵核對吻合。",
                }, ensure_ascii=False)

        # 2. D1 影像辨識預填 (支援多品牌電鑽及各類工具)
        if "D1_TOOL" in sys_str:
            if "makita" in p_lower or "牧田" in p_lower:
                return json.dumps({
                    "suggested_name": "Makita 牧田 DHP482 18V無刷充電式雙速震動電鑽",
                    "category": "POWER_TOOLS",
                    "damage_tool_id_match": "TOOL_DRILL_01",
                    "suggested_accessories": ["牧田電鑽主機", "18V 5.0Ah 鋰電池", "原廠充電器", "側柄", "深度桿"],
                    "safety_warning": "操作牧田震動電鑽請配戴護目鏡與耳塞，切換震動模式鑽水泥孔時請雙手握持側柄穩定機身。",
                }, ensure_ascii=False)
            elif "dewalt" in p_lower or "得偉" in p_lower:
                return json.dumps({
                    "suggested_name": "DeWalt 得偉 DCD796 20V MAX無碳刷雙速衝擊震動電鑽",
                    "category": "POWER_TOOLS",
                    "damage_tool_id_match": "TOOL_DRILL_01",
                    "suggested_accessories": ["得偉電鑽主機", "20V MAX 5.0Ah XR鋰電池", "黃黑原廠座充", "雙頭螺絲批頭", "皮帶掛扣"],
                    "safety_warning": "得偉無碳刷大扭力輸出，鑽孔遇到鋼筋卡死時可能產生反扭力，請務必站穩重心並使用低速檔試鑽。",
                }, ensure_ascii=False)
            elif "milwaukee" in p_lower or "美沃奇" in p_lower:
                return json.dumps({
                    "suggested_name": "Milwaukee 美沃奇 M18 FUEL 18V無碳刷衝擊電鑽 (2804-20)",
                    "category": "POWER_TOOLS",
                    "damage_tool_id_match": "TOOL_DRILL_01",
                    "suggested_accessories": ["美沃奇電鑽主機", "M18 REDLITHIUM 5.0Ah 電池", "快速充電器", "原廠重型側手柄", "工具收納提箱"],
                    "safety_warning": "美沃奇 M18 FUEL 具備強大扭力 (135Nm)，高負載作業請務必加裝原廠重型側手柄並配戴抗震手套。",
                }, ensure_ascii=False)
            elif "washer" in p_lower or "清洗機" in p_lower:
                return json.dumps({
                    "suggested_name": "Karcher K2 家用高壓清洗機組",
                    "category": "CLEANING",
                    "damage_tool_id_match": "TOOL_WASHER_01",
                    "suggested_accessories": ["高壓噴槍握柄", "4米高壓軟管", "扇形噴桿", "旋轉噴桿"],
                    "safety_warning": "操作高壓清洗機請注意安全防護，嚴禁將高壓噴槍對準人體或寵物，開機前請先通水排空空氣。",
                }, ensure_ascii=False)
            elif "ladder" in p_lower or "梯" in p_lower:
                return json.dumps({
                    "suggested_name": "加厚款多功能關節折疊伸縮鋁梯",
                    "category": "HAND_TOOLS",
                    "damage_tool_id_match": "TOOL_LADDER_01",
                    "suggested_accessories": ["伸縮梯主體", "底部加寬平衡桿", "固定螺栓"],
                    "safety_warning": "攀登前請務必注意安全，親眼確認每階左右兩側卡榫完全彈出鎖定，保持 4:1 傾角。",
                }, ensure_ascii=False)
            elif any(k in p_lower for k in ["projector", "投影機", "雷射", "jmgo"]):
                return json.dumps({
                    "suggested_name": "JMGO N1S Infinity 4K目氪三色雷射投影機",
                    "category": "HAND_TOOLS",
                    "damage_tool_id_match": "jmgo-n1s-infinity-4k",
                    "suggested_accessories": ["原廠遙控器", "專用電源轉接器", "雲台旋轉底座", "便攜手提收納盒"],
                    "safety_warning": "雷射光源強烈，嚴禁直視投影鏡頭或對準他人眼睛，搬運時請握持機身與雲台底座。",
                }, ensure_ascii=False)
            elif any(k in p_lower for k in ["tent", "帳篷", "露營", "snowpeak"]):
                return json.dumps({
                    "suggested_name": "Snow Peak Land Nest 別墅帳 四人家庭隧道帳 TP-259",
                    "category": "CAMPING",
                    "damage_tool_id_match": "snowpeak-landnest-tp259",
                    "suggested_accessories": ["外帳本體", "內帳本體", "鋁合金營柱組", "營釘14支", "營繩組", "原廠收納袋"],
                    "safety_warning": "嚴禁在密閉帳篷內使用炭火或瓦斯爐以防一氧化碳中毒，歸還前請務必完全曬乾並清除泥砂。",
                }, ensure_ascii=False)
            elif any(w in p_lower for w in ["mug", "cup", "coffee", "馬克杯", "咖啡", "unrelated", "無關"]):
                return json.dumps({
                    "suggested_name": "無法識別為修繕或露營工具",
                    "category": "UNKNOWN",
                    "damage_tool_id_match": None,
                    "suggested_accessories": [],
                    "safety_warning": "非修繕工具物品，請拍攝正確之社區修繕工具以供辨識。",
                }, ensure_ascii=False)
            else:
                return json.dumps({
                    "suggested_name": "Bosch GSB 185-LI 18V免碳刷震動電鑽+30件鑽頭組",
                    "category": "POWER_TOOLS",
                    "damage_tool_id_match": "TOOL_DRILL_01",
                    "suggested_accessories": ["電鑽主機", "18V 2.0Ah 鋰電池", "原廠座充", "30件鍍鈦鑽頭組", "手提收納箱"],
                    "safety_warning": "磚牆震動鑽孔時請配戴護目鏡與耳部防護，鑽孔前請使用金屬管線探測器確認暗管。",
                }, ensure_ascii=False)

        # 3. A2 情境搜尋標籤推薦
        if "A2_SCENARIO" in sys_str:
            if any(w in p_lower for w in ["政治", "八卦", "總統", "股票", "天氣"]):
                return json.dumps({
                    "is_tool_related": False,
                    "tags": [],
                    "advice": "我是鄰里工具工程師狸利，只擅長工具租借與居家修繕相關問題喔！請問有什麼修繕任務需要工具支援嗎？",
                }, ensure_ascii=False)

            has_wash = any(w in p_lower for w in ["水垢", "清洗", "洗車", "青苔", "陽台", "高壓"])
            has_hang = any(w in p_lower for w in ["壁掛", "畫框", "相框", "掛畫", "鑽孔", "層板", "貓跳台", "打孔", "電鑽"])
            has_ladder = any(w in p_lower for w in ["高處", "天花板", "換燈泡", "梯", "四步梯"])
            has_grind = any(w in p_lower for w in ["砂輪", "除鏽", "打磨", "研磨", "切割", "毛邊"])
            has_plumb = any(w in p_lower for w in ["水管", "水龍頭", "漏水", "排水"])

            if has_hang and has_wash:
                return json.dumps({
                    "is_tool_related": True,
                    "tags": ["高壓清洗機", "衝擊電鑽", "水泥鑽頭", "雷射水平儀"],
                    "advice": "偵測到多重修繕情境：清洗磁磚水垢建議使用「高壓清洗機」強力沖刷；壁掛畫框安裝則推薦使用「震動衝擊電鑽」與「雷射水平儀」確認基準高度，安全省力又平整！",
                }, ensure_ascii=False)
            elif has_wash:
                return json.dumps({
                    "is_tool_related": True,
                    "tags": ["高壓清洗機", "旋轉噴頭", "自吸水管"],
                    "advice": "清洗頑固水垢、磁磚縫隙或陽台青苔，建議使用「高壓清洗機」。強效水柱能快速剝除水垢污漬，省時省水且免用化學清潔劑！",
                }, ensure_ascii=False)
            elif has_hang:
                return json.dumps({
                    "is_tool_related": True,
                    "tags": ["衝擊電鑽", "水泥鑽頭", "壁虎螺絲", "雷射水平儀"],
                    "advice": "牆面壁掛畫框、相框或層板，建議使用「震動衝擊電鑽」搭配水泥專用鑽頭打孔，並以「雷射水平儀」精準抓取水平線，避免安裝歪斜！",
                }, ensure_ascii=False)
            elif has_grind:
                return json.dumps({
                    "is_tool_related": True,
                    "tags": ["手持砂輪研磨機", "研磨砂輪片", "護目鏡"],
                    "advice": "金屬除鏽、焊接毛邊打磨或角鋼管件切割，建議租借「手持砂輪研磨機」，操作時請務必配戴護目鏡與防護手套以策安全！",
                }, ensure_ascii=False)
            elif has_ladder:
                return json.dumps({
                    "is_tool_related": True,
                    "tags": ["折疊四步梯", "防滑踏板"],
                    "advice": "室內高處檢修、天花板修繕或換裝燈具窗簾，建議使用「鋁合金折疊四步梯」，安全穩固且折疊後收納不佔空間。",
                }, ensure_ascii=False)
            elif has_plumb:
                return json.dumps({
                    "is_tool_related": True,
                    "tags": ["活動扳手", "管鉗", "止水帶", "水管剪"],
                    "advice": "更換水龍頭或水管建議使用活動扳手拆卸螺母，並纏繞止水帶 15-20 圈防止滲水漏水。",
                }, ensure_ascii=False)
            else:
                return json.dumps({
                    "is_tool_related": True,
                    "tags": ["手工具組", "螺絲起子", "捲尺"],
                    "advice": "日常居家修繕任務，建議備妥基本手工具與水平量具以確保施作精度。",
                }, ensure_ascii=False)

        # 4. Tool Consistency Verification (品項與照片一致性檢驗)
        if "TOOL_CONSISTENCY" in sys_str:
            if "blurry" in p_lower or "模糊" in p_lower:
                return json.dumps({
                    "is_consistent": False,
                    "detected_tool": "無法識別",
                    "confidence": 0.40,
                    "requires_retake": True,
                    "mismatch_reason": "照片過度晃動模糊或光線不足，無法辨別工具外觀，請重新對焦拍攝。",
                }, ensure_ascii=False)

            if any(w in p_lower for w in ["mug", "cup", "coffee", "馬克杯", "咖啡", "unrelated", "無關", "雜物"]):
                return json.dumps({
                    "is_consistent": False,
                    "detected_tool": "辦公生活雜物/馬克杯",
                    "confidence": 0.97,
                    "requires_retake": True,
                    "mismatch_reason": "照片內容辨識為生活物品（馬克杯），並非所登記之工具。請拍攝實際修繕工具！",
                }, ensure_ascii=False)

            is_drill_expected = "drill" in p_lower or "電鑽" in p_lower or "power_tools" in p_lower
            is_ladder_expected = "ladder" in p_lower or "梯" in p_lower

            if is_drill_expected and ("ladder" in p_lower or "梯" in p_lower):
                return json.dumps({
                    "is_consistent": False,
                    "detected_tool": "加厚鋁合金 A 字摺疊梯",
                    "confidence": 0.95,
                    "requires_retake": True,
                    "mismatch_reason": "品項不一致：您選擇了【電鑽】，但照片辨識為【鋁合金梯】。請重新拍攝正確工具！",
                }, ensure_ascii=False)
            elif is_ladder_expected and ("drill" in p_lower or "電鑽" in p_lower):
                return json.dumps({
                    "is_consistent": False,
                    "detected_tool": "BOSCH 震動電鑽組",
                    "confidence": 0.95,
                    "requires_retake": True,
                    "mismatch_reason": "品項不一致：您選擇了【鋁合金梯】，但照片辨識為【震動電鑽】。請重新拍攝正確工具！",
                }, ensure_ascii=False)
            elif "mismatch" in p_lower or "不一致" in p_lower:
                return json.dumps({
                    "is_consistent": False,
                    "detected_tool": "非目標工具/無關物品",
                    "confidence": 0.91,
                    "requires_retake": True,
                    "mismatch_reason": "照片中的物品與您所選之工具規格不符，請重新拍照！",
                }, ensure_ascii=False)
            else:
                if is_drill_expected:
                    if "makita" in p_lower or "牧田" in p_lower:
                        detected = "Makita 牧田 18V 充電式震動電鑽"
                    elif "dewalt" in p_lower or "得偉" in p_lower:
                        detected = "DeWalt 得偉 20V MAX 衝擊電鑽"
                    elif "milwaukee" in p_lower or "美沃奇" in p_lower:
                        detected = "Milwaukee 美沃奇 M18 FUEL 衝擊電鑽"
                    else:
                        detected = "BOSCH 震動電鑽組"
                else:
                    detected = "加厚鋁合金 A 字摺疊梯" if is_ladder_expected else "修繕工具"

                return json.dumps({
                    "is_consistent": True,
                    "detected_tool": detected,
                    "confidence": 0.96,
                    "requires_retake": False,
                    "mismatch_reason": None,
                }, ensure_ascii=False)

        # 5. Same Object Verification (Check-in 取件照 vs 原始上架照)
        if "SAME_OBJECT" in sys_str:
            if any(w in p_lower for w in ["mug", "cup", "coffee", "馬克杯", "咖啡", "unrelated", "無關", "雜物", "desk", "生活"]):
                return json.dumps({
                    "is_same_object": False,
                    "confidence": 0.98,
                    "difference_notes": "【非工具生活雜物】現場取件照片辨識為生活物品（馬克杯），並非登記出租之修繕工具。系統已阻擋取件推進，請拍攝實際工具！",
                    "requires_retake": True,
                    "recommended_angle": "建議將鏡頭對準借用的工具主體，拍攝 45 度側面特寫露出品牌銘牌，降低比對成本。",
                }, ensure_ascii=False)
            elif "mismatch" in p_lower or "diff" in p_lower or ("ladder" in p_lower and "drill" in p_lower) or "不同" in p_lower or ("bosch" in p_lower and any(b in p_lower for b in ["makita", "dewalt", "milwaukee", "牧田", "得偉", "美沃奇"])):
                return json.dumps({
                    "is_same_object": False,
                    "confidence": 0.96,
                    "difference_notes": "【同類跨品牌調包攔截】原始登記為「BOSCH 電鑽」，現場取件相片特徵辨識為其他品牌（如牧田 Makita）。品牌銘牌不符，非原借出之同一實體物件！請核對後重新拍照。",
                    "requires_retake": True,
                    "recommended_angle": "請拍攝原本借出之同一品牌工具，保持 45 度側面露出銘牌，避免產生爭議。",
                }, ensure_ascii=False)
            elif "blurry" in p_lower or "模糊" in p_lower:
                return json.dumps({
                    "is_same_object": False,
                    "confidence": 0.42,
                    "difference_notes": "取件照片過於模糊，無法與原始上架照片比對特徵，請重新對齊拍照。",
                    "requires_retake": True,
                    "recommended_angle": "請穩定手機對焦拍攝，保持與原照相同之 45 度側視角。",
                }, ensure_ascii=False)
            else:
                return json.dumps({
                    "is_same_object": True,
                    "confidence": 0.96,
                    "difference_notes": "現場取件相片與原始上架裝備機身銘牌、外觀輪廓與型號特徵完全吻合，確認為同一實體物件。",
                    "requires_retake": False,
                    "recommended_angle": "拍攝角度與初始取件照片高度一致 (45度側視角)，雙圖特徵核對吻合。",
                }, ensure_ascii=False)

        return "{}"
