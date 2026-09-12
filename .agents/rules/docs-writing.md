---
description: 鄰里工具 (LinLi Tool) 文檔撰寫與合規守則 (Documentation Writing & Compliance Guidelines)
globs: ["**/*.md", "docs/**"]
---

# LinLi Tool (鄰里工具) - 文檔撰寫與合規標準規範

本規範定義專案內所有技術文檔、架構規格（PRD / SPEC）、操作指引、API 說明與 README 之撰寫準則，以確保文檔的一致性、工程精確度與主管機關法規遵循。

---

## 一、語系與排版風格規範

1. **預設繁體中文 (Traditional Chinese)**：
   - 所有面向使用者、社群住戶、管理員與開發團隊之文檔說明，一律使用台灣繁體中文。
   - 專有名詞、代碼符號、API 路徑與 HTTP Method 保留標準英文（如 `FastAPI`、`POST /api/v1/orders/{id}/check-in`、`SHA-256`、`Gemini Vision`）。
2. **GitHub Flavored Markdown (GFM)**：
   - 標題階層嚴格遞進（`#` -> `##` -> `###`），禁止跳級。
   - 代碼區塊必須標註語言類型（如 `bash`、`python`、`typescript`、`json`、`text`）。
   - 關鍵提示與警告，統一採用 GitHub Alert 語法（`> [!NOTE]`、`> [!TIP]`、`> [!IMPORTANT]`、`> [!WARNING]`）。
3. **架構與時序視覺化 (Mermaid Diagrams)**：
   - 涉及多方交互之流程（如 TOTP 見面取件、歸還雙階段門禁、保障池責任扣抵與補貼），文檔中必須搭配 Mermaid 流程圖或時序圖輔助說明。

---

## 二、金融微文案合規原則 (Zero Forbidden Words)

依據金管會與消保法規標準，本互助平台非特許保險機構，所有文檔中**絕對嚴禁出現任何保險法特許名詞**：

| ❌ 絕對嚴禁詞彙 | ✅ 法定合規專有名詞 | 文檔撰寫情境範例 |
| :--- | :--- | :--- |
| **保險** | **互助保障池** / **社區互助保障** | 「損壞超出押金部分，由社區**互助保障池**啟動補貼」 |
| **保費** | **互助保障金** / **設備維護費** | 「每筆訂單內含 5% **互助保障金**以充實保障池底蘊」 |
| **理賠** | **責任補貼** / **損害補償** | 「經審核後核發最高 70% 之**責任補貼**款項」 |

> [!WARNING]
> 所有文檔發佈或更新前，必須落實「保險 / 保費 / 理賠」0 次違規詞檢核。

---

## 三、Vision AI 雙階段驗收與成本規範文案

在描述影像核銷、取件或歸還流程時，文檔必須忠實呈現以下架構：

1. **兩階段門禁原則 (Two-Stage Inspection Gate)**：
   - **第一道門禁：物品有效性與同實體檢核**（非關雜物 `INVALID_OBJECT` 與品牌調包 `TOOL_SWAP_DETECTED` 先行阻斷，HTTP 422）。
   - **第二道門禁：差分損壞評估**（通過同物件檢核後，方可進入 MATCH / MINOR_DIFF / DAMAGE_DETECTED 責任計算）。
2. **Fail-Closed 容錯描述**：
   - 文檔應明確記錄：未通過辨識或照片模糊者，系統一律預設為 `requires_retake=True` 與 `is_same_object=False`，拒絕取件/歸還，清空 SHA-256 存證雜湊，訂單維持在原狀態，絕對禁止推進至 `IN_USE`。
3. **45 度角與 258 Tokens 成本優化**：
   - 使用者拍照指引必須明確標註：**「45 度側身特寫，露出品牌 LOGO 與夾頭銘牌」**。
   - 明確說明 Token 優化成效：透過 Canvas 768px 邊緣等比壓縮，將單次呼叫鎖定在 1 個 Tile (258 Tokens，節省 93% 頻寬與費用)。

---

## 四、技術文檔必備結構標準

撰寫功能規格書或 API 說明文件時，應涵蓋以下核心段落：
1. **背景與業務目標 (Context & Objectives)**：該功能欲解決之社區痛點與預期成效。
2. **架構與時序流程 (Architecture & Sequence)**：前端互動、後端服務、AI Gateway 與資料庫之數據流。
3. **API 規格與資料模型 (API Specs & Data Models)**：請求路徑、Headers、Payload 範例、回傳結構與 HTTP 狀態碼（包含 422 錯誤原因）。
4. **極端案例與防呆處理 (Edge Cases & Guardrails)**：頻率限制 (Rate Limit)、超時降級 (Fallback)、模糊照片 0-Token 秒判。
5. **測試與驗證方式 (Verification & Test Cases)**：對應的自動化測試指令（如 `pytest tests/test_ai_gateway.py`）與手動驗收步驟。
