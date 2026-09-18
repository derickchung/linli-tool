---
name: robust-engineering
description: 泛化軟體工程規範、全鏈路契約透傳、變更對稱性、防禦性變數生命週期與強型別邊界守則
---

# 泛化強健工程規範 (Universal Robust Engineering Invariants)

本規範定義所有軟體開發、跨端資料流轉與 AI 輔助協同編程時必須遵循的**不可逾越工程原則（Engineering Invariants）**。其核心宗旨是：**「將系統強健性建立在編譯期檢查、強型別契約與架構約束上，杜絕因人為或 AI 疏忽引發的低階運行期崩潰。」**

---

## 一、 契約驅動與全鏈路透傳原則 (Contract-First & Pipeline Integrity)

### 1. 單一真實來源 (Single Source of Truth, SSOT)
- 所有跨行程、跨端或跨模組的資料互動，必須在架構邊界定義嚴格的 Data Contract（DTO / Schema / Interface）。
- 資料模型欄位定義即為系統法典，任何欄位異動必須首先在 Schema 層完成宣告。

### 2. 禁止隨興過濾（No Ad-hoc Stripping）
- 當資料流經多層架構（如：`UI Component` ➔ `Service Layer` ➔ `HTTP Client` ➔ `Network Payload` ➔ `Backend Router` ➔ `Domain Model`）時：
  - **中間傳輸層嚴禁宣告殘缺的物件字面量（Object Literals）逐欄白名單拼裝**。
  - 轉發必須採用完整型別透傳或強型別序列化（Spread Operator / Serializer），保證上游合法資料 100% 完整傳遞至下游，杜絕靜默丟棄欄位。

---

## 二、 變更對稱性法則 (The Law of Symmetric Refactoring)

### 1. 全鏈路 4 端點對稱審查
凡新增、修改或更名任何業務欄位時，重構範圍必須**同時且對稱地覆蓋整條資料鏈的 4 個端點**：
1. **產生端 (Producer)**：前端表單、業務運算或資料提取層。
2. **傳輸包裝層 (Transport / Client)**：HTTP Client 請求組裝、序列化與 Headers 注入。
3. **接收解構層 (Receiver / Controller)**：後端 Schema 反序列化、Controller / Router 路由注入。
4. **測試與備援層 (Fallback / Mock)**：Mock 假資料生成器、單元測試測資與降級容錯分支。

### 2. 嚴禁「頭尾重構」
嚴禁只修改產生端與接收端，卻留下一知半解或欄位遺漏的中間轉發層。

---

## 三、 防禦性範疇與零未綁定原則 (Zero-Unbound & Scope Invariance)

### 1. 函式頂層全量顯式初始化 (Top-Level Explicit Initialization)
- 在 Python、JavaScript/TypeScript 等語言中，**凡是在 `if/elif/else`、`switch/case`、迴圈、或 `try/catch` 分支內部被賦值的區域變數，必須在該函式或區塊的第一行完成顯式初始化**（給予安全預設值，如 `None`、`null`、空集合或預設 Sentinel）。
- **零未綁定保證 (Zero-Unbound Guarantee)**：任何變數在被讀取或做條件判斷（如 `if not var:`）前，必須 100% 保證具備已指派的記憶體狀態，**從物理架構上徹底根絕直譯器層級的 `UnboundLocalError` 或 Null Pointer Exception**。

### 2. 窮盡性分支 (Exhaustive Branching)
- 任何條件判斷必須妥善處理「全非情況（Fallback / Default Case）」，絕不可留有未處理的懸空變數或邏輯死角。

---

## 四、 強型別邊界與弱型別零容忍 (Strict Boundary Typing)

### 1. 強制使用結構化模型（Schema-First）
- 後端接收請求時，**嚴禁使用無型別的裸字典提取（如 `request.json()`、`body.get("key")`、`params["key"]`）**。
- 必須透過強型別驗證框架（如 Pydantic BaseModel、Zod、Protobuf）自動反序列化。所有非必填欄位必須顯式宣告預設值（例如 `field: Optional[T] = None`）。

### 2. 前端編譯期鎖定
- 前端發送請求必須使用 TypeScript Strict Interface，禁止使用 `any` 或任意忽略編譯器檢查（禁止無故使用 `@ts-ignore`）。

---

## 五、 非對稱變異驗證 (Payload Mutation & Degraded Path Verification)

### 1. 殘缺資料變異測試（Mutation Check）
在實作或修復任何功能時，必須主動驗證以下 3 種邊界：
1. **全空/部分空值**：當可選欄位全部未傳入時，系統是否平滑容錯？絕不允許拋出未捕獲的 500 內部伺服器崩潰。
2. **型別異常值**：傳入非預期格式字串或邊界值時，應由 Schema 拋出可讀的 422 錯誤，而非 500 崩潰。
3. **下游中斷與 Fail-Closed**：當依賴的外部模組（如 AI Gateway、遠端金鑰、資料庫連線）異常時，系統必須遵循 **Fail-Closed 原則（安全阻斷並明確反饋使用者）**，保持狀態機清潔，禁止髒資料推進。

---

## 六、 程式碼審查檢查清單 (Self-Check Checklist)

提交任何程式碼修改前，必須逐項過濾以下自檢表：
- [ ] **Data Flow**：本變更涉及的欄位，在 UI ➔ Service ➔ API Client ➔ Router ➔ DB 中是否全鏈路對齊？
- [ ] **Variable Scope**：所有在分支內被賦值的變數，函式開頭是否皆有顯式初始化？
- [ ] **Typing**：是否杜絕了任何 `request.json()` 或裸字典 `get()`？是否使用 Pydantic Model？
- [ ] **Resilience**：若請求 Payload 完全缺失可選欄位，端點是否保證回傳合法響應而非 500？
