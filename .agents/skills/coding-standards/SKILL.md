---
name: coding-standards
description: LinLi Tool 程式碼風格標準、型別安全、繁體中文註釋與合規靜態審核規範
---

# LinLi Tool (鄰里工具) - 程式碼撰寫與風格規範 (Coding Standards Guide)

本規範定義 LinLi Tool 全專案之後端 (Python)、前端 (TypeScript/React) 之編碼風格、型別安全、架構防禦與微文案合規標準。

---

## 一、 核心開發哲學

1. **防禦性設計 (Defensive by Design)**：所有外部輸入（包含相片、Query 參數、表單欄位）皆視為不可信，必須經過 Pydantic 或前端 Schema 嚴密校驗。
2. **Fail-Closed 預設防呆**：遇到未知異常或非預期格式，一律預設為拒絕放行並要求重試，禁止寬鬆放行。
3. **金融監理 0 次違規詞**：程式碼內部常數、錯誤訊息、UI 文案與註釋，嚴禁出現「保險 / 保費 / 理賠」。
4. **高可維護性**：以繁體中文撰寫關鍵商業邏輯 Docstrings 與註釋。

---

## 二、 後端 Python (FastAPI / SQLAlchemy / Pydantic) 規範

### 1. 型別提示與 Pydantic v2 驗證
- 所有函式參數與回傳值必須標註型別提示（Type Hints）。
- API Request / Response 必須使用繼承自 `pydantic.BaseModel` 的專用 Schema，並宣告欄位驗證約束：
  ```python
  class DisputeCreateRequest(BaseModel):
      order_id: int = Field(..., description="關聯之訂單 ID")
      reason: str = Field(..., min_length=5, description="申訴原因與異議說明")
      evidence_photos: Optional[List[str]] = Field(default_factory=list, description="佐證照片網址清單")
  ```

### 2. SQLAlchemy 資料存取規範
- **多租戶隔離**：所有查詢必須主動過濾 `community_id`，嚴禁裸查造成跨社區資料外洩。
- **防止 SQL 注入**：一律使用 SQLAlchemy ORM 或帶參數之 Prepared Statements，嚴禁使用 f-string 拼接 SQL。
- **交易原子性**：狀態變更與扣抵操作必須置於 `db.commit()` 中，發生例外時即刻執行 `db.rollback()`。

### 3. 例外處理與 HTTP 狀態碼
- 嚴禁靜默吞掉例外（Empty `except:`）。
- 精準拋出標準 FastAPI `HTTPException`：
  - `400 Bad Request`：非法業務參數（如租借自己上架的工具）。
  - `403 Forbidden`：越權操作（非訂單當事人試圖申訴爭議）。
  - `404 Not Found`：查無實體。
  - `409 Conflict`：時段預約並發衝突。
  - `422 Unprocessable Entity`：門禁攔截（生活雜物 `INVALID_OBJECT`、品牌調包 `TOOL_SWAP_DETECTED`）。
  - `429 Too Many Requests`：AI Gateway 頻率限制。

---

## 三、 前端 TypeScript / React 規範

### 1. 嚴格型別 (Strict Typing)
- 嚴禁濫用 `any`。所有 API 回傳資料必須在 `frontend/src/types/` 定義對應的 TypeScript Interface。
- 善用 Union Types 與字面量型別表示狀態機：
  ```typescript
  export type OrderStatus = 
    | 'CONFIRMED' 
    | 'PICKED_UP' 
    | 'IN_USE' 
    | 'INSPECTION' 
    | 'DISPUTED' 
    | 'COMPLETED' 
    | 'CANCELLED';
  ```

### 2. 元件架構與 Hooks 組織
- 元件檔名採用 `PascalCase`（如 `CheckOutOverlay.tsx`），自訂 Hook 採用 `camelCase`（如 `useOrderState.ts`）。
- 邏輯與視覺分離：商業邏輯、API 呼叫與計算抽離為 Custom Hook，UI 元件專注於渲染與事件綁定。

### 3. 前端防呆防線
- 涉及按鈕防點擊：進行中之非同步操作（`isSubmitting`）必須同步停用按鈕並呈現 Loading Spinner。
- 相片上傳必須透過 Canvas 邊緣壓縮至最長邊 768px 後方可送出。

---

## 四、 註釋與文檔規範 (Documentation & Comments)

1. **模組與函式 Docstring**：
   - 包含簡明繁體中文說明、核心門禁規則與預期例外：
   ```python
   def verify_same_object(...) -> Dict[str, Any]:
       """
       Check-in 取件雙圖同物件比對 (Checkin vs Listing Original Photo)
       - 確認現場取件相片與出借人原上架照為同一實體。
       - 攔截非工具生活雜物 (INVALID_OBJECT) 與同類品牌調包 (TOOL_SWAP_DETECTED)。
       """
   ```
2. **禁止事項**：
   - 嚴禁在程式碼中殘留「放行 Mock 破口」（例如 `return True # TODO: fix later`）。
   - 嚴禁遺留未處理之 console.log 或除錯列印。
