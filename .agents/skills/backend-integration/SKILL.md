---
name: backend-integration
description: LinLi Tool 前後端整合協議、RESTful API 契約、AI Gateway 直通端點與異常處理指南
---

# LinLi Tool (鄰里工具) - 前後端整合開發規範 (Backend Integration Guide)

本規範定義 LinLi Tool 前端 (React) 與後端 (FastAPI) 之間的通訊契約、API 端點清單、Payload 傳輸規格、AI Gateway 直通與例外處理準則。

---

## 一、 通訊架構與基本配置

1. **基本連線資訊**：
   - **後端服務基底路徑**：`http://127.0.0.1:8000/api/v1`
   - **API 互動文檔**：`http://127.0.0.1:8000/docs` (Swagger UI)
   - **前端開發代理 (Vite Proxy)**：`frontend/vite.config.ts` 設定將 `/api` 請求無縫轉發至 `http://localhost:8000`。
2. **認證標頭規範 (JWT Authentication)**：
   - 需授權之請求必須攜帶：`Authorization: Bearer <access_token>`。
   - 住戶必須具備 `VALIDATED` (社區已驗證) 狀態，方能進行預約、發起借用或建立工具。

---

## 二、 六大分頁核心 API 契約矩陣

### TAB 1: 工具探索與費用試算
- `GET /items/`：取得當前社區工具清單與可用狀態。
- `POST /rag/recommend`：
  - **Request**：`{ "prompt": "自然語言修繕需求，如：水垢清洗" }`
  - **Response**：`{ "tags": ["高壓清洗機", "旋轉噴頭"], "advice": "..." }`
- `POST /orders/calculate`：
  - **Request**：`{ "item_id": 1, "start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD" }`
  - **Response**：`{ "total_rent": 600, "base_deposit": 4500, "actual_deposit": 1125, "authorized_total": 1725, ... }`

### TAB 2: D1 工具拍照辨識上架
- `POST /items/recognize`：
  - 支援 Multipart 或 Query `filename_hint`，回傳工具品牌、建議品名、配件與安全操作指引。
  - **嚴格防呆**：回傳中嚴禁包含價格，`daily_rate` 與 `market_value` 留空由前端引導用戶手動定價。
- `POST /items/verify-consistency`：
  - **Request**：`{ "expected_name": "電鑽", "filename_hint": "drill.jpg" }`
  - **Response**：`{ "is_consistent": bool, "requires_retake": bool, "mismatch_reason": str }`
- `POST /items/`：建立新工具 (需驗證住戶權限)。

### TAB 3: 訂單交付與現場取件 Check-in
- `GET /orders/{id}/handover/code`：借用人取得 6 碼動態 TOTP 碼與過期秒數。
- `POST /orders/{id}/handover/verify`：出借人核銷 TOTP，狀態推進至 `PICKED_UP`。
- `POST /items/verify-same-object` (現場同物件核驗)：
  - **Request**：`{ "item_name": str, "original_image_url": str, "image_base64": str }`
  - **Response**：`{ "is_same_object": bool, "confidence": float, "difference_notes": str, "recommended_angle": str }`
- `POST /orders/{id}/check-in`：確認同物件核驗通過後，寫入 SHA-256 Checksum 並推進訂單至 `IN_USE`。

### TAB 4: 歸還驗收雙圖差分 Check-out
- `POST /orders/{id}/check-out`：
  - **Request**：`{ "image_url": str, "image_base64": str, "notes": str }`
  - **兩階段門禁檢核**：
    - 若判定為非關雜物 (`INVALID_OBJECT`) 或品牌調包 (`TOOL_SWAP_DETECTED`)：拋出 **HTTP 422 Unprocessable Entity**。
    - 若為正常耗損 (`MATCH`)：回傳 HTTP 200，退還押金並獎勵信用分。
    - 若為磨損或損壞 (`MINOR_DIFF` / `DAMAGE_DETECTED`)：推進至 `INSPECTION`，啟動責任比例試算。

### TAB 5: 爭議調解工單
- `POST /disputes/`：
  - **Request**：`{ "order_id": int, "reason": str, "evidence_photos": [str] }`
  - **權限約束**：僅限該訂單之借用人或出借人發起 (非當事人回傳 HTTP 403)。
- `GET /disputes/{id}`：查詢爭議進度與原始存證相片。
- `PATCH /disputes/{id}/resolve`：管委會/管理員覆核結案。

### TAB 6: 社區互助保障池
- `GET /orders/pool/status`：查詢即時公庫餘額 (`current_balance`)、累計注資 (`total_inflow`)、累計支出 (`total_outflow`)。
- `GET /orders/pool/payouts`：取得歷史責任補貼明細清單。

---

## 三、 多模態照片傳輸與邊緣壓縮最佳實踐

1. **前端 Canvas 等比壓縮 (Tier 0)**：
   - 上傳相片前，前端必須使用 Canvas 將影像等比縮小至最長邊 `768px`，品質設定為 JPEG `0.85`。
   - 效益：將多模態請求限制在 1 個 Gemini Tile (258 Tokens)，杜絕高頻寬浪費。
2. **Payload 封裝標準**：
   - 優先支援 Base64 Data URL (`data:image/jpeg;base64,...`)，後端自動剝離 Header 轉為 Byte 流。

---

## 四、 AI Gateway 速率限制 (Rate Limit) 處置

後端 `AIGateway` 針對各住戶設置有保護機制：
- **限制標準**：每位住戶每分鐘最多 5 次 AI 呼叫。
- **超額響應**：回傳 **HTTP 429 Too Many Requests** (`AI 呼叫次數已達上限，請稍候再試`)。
- **前端對策**：
  - 遇到 429 時，UI 應呈現「AI 分析冷卻中 (請稍候 30 秒)」之友善提示框，避免使用者連續狂點。

---

## 五、 金融微文案契約合規檢核

API 回傳之所有 `message`, `detail`, `advice`, `breakdown_title` 欄位：
- 嚴格禁止包含：「保險」、「保費」、「理賠」。
- 一律採用：「互助保障池」、「維護費（保障金）」、「責任補貼（損害補償）」。
