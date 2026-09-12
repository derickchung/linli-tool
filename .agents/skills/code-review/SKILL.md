---
name: code-review
description: LinLi Tool 程式碼審查清單 (Code Review Checklist)、安全性門禁、法規合規與 PR 合併準則
---

# LinLi Tool (鄰里工具) - 程式碼審查標準 (Code Review Checklist)

本規範定義 LinLi Tool 專案在進行 Pull Request (PR)、程式碼審查 (Code Review) 或自我驗收時的強制檢核清單與拒絕標準。

---

## 一、 程式碼審查總體原則

任何涉及核心業務變更之 PR，必須通過 **「門禁防禦、Fail-Closed 防呆、Token 成本控制、金融法規微文案、多租戶安全」** 五大維度檢核，任一維度違規即予以駁回 (Block)。

---

## 二、 五大核心維度審查清單 (Checklist)

### 1. Vision AI 雙階段門禁檢核 (Two-Stage Gate)
- [ ] **第一道門禁非關物品阻斷**：上傳馬克杯、文具等生活雜物，是否即刻拋出 HTTP 422 `INVALID_OBJECT`？
- [ ] **第一道門禁品牌調包阻斷**：同品類跨品牌（如借 Bosch 拍牧田 Makita），是否精準判定為 `TOOL_SWAP_DETECTED`？
- [ ] **差分順序保護**：是否保證「僅在同物件驗證通過後」才進行第二道損壞差分與責任計算？
- [ ] **狀態鎖定**：比對未通過時，是否嚴格鎖定按鈕，禁止訂單推進至 `IN_USE` 或 `COMPLETED`？

### 2. Fail-Closed 預設關閉防呆檢核
- [ ] **零寬鬆放行**：後端或 Mock 降級邏輯中，是否徹底杜絕「只要不是特定錯誤就預設放行」的設計？
- [ ] **預設重拍**：對未知照片、格式異常或低信心度推論，是否一律預設為 `requires_retake=True` 與 `is_same_object=False`？
- [ ] **存證雜湊清空**：核驗失敗時，前端與後端是否同步清空 SHA-256 存證雜湊？

### 3. 45 度角指引與 258 Tokens 成本檢核
- [ ] **邊緣壓縮防線 (Tier 0)**：前端是否在 Canvas 進行最長邊 768px 等比壓縮？
- [ ] **Token 鎖定**：是否確保 Gemini 多模態呼叫限制在 1 個 Tile (258 Tokens)？
- [ ] **本機秒判防線 (Tier 1)**：後端對全黑或嚴重模糊廢照，是否使用 Pillow 進行 0-Token 秒判攔截？
- [ ] **角度引導提示**：相機取景介面是否明確提示借用人「45 度側身特寫，露出品牌 LOGO 與夾頭銘牌」？

### 4. 金融監理微文案合規檢核 (Zero Forbidden Words)
- [ ] **0 次違規詞**：全檔案（包含註釋、API 訊息、前端 UI、RAG 知識庫）嚴格無以下詞彙：
  - ❌ 禁止出現：「保險」、「保費」、「理賠」
- [ ] **法定名詞替代**：
  - ✅ 是否採用「互助保障池」？
  - ✅ 是否採用「維護保障金」或「維護費」？
  - ✅ 是否採用「責任補貼」或「損害補償」？

### 5. 多租戶隔離與系統安全檢核
- [ ] **社區邊界隔離**：所有查詢是否均包含 `community_id` 過濾，防範跨社區越權 (IDOR)？
- [ ] **並發排他排程鎖**：建立訂單時是否正確偵測並發檔期衝突並回傳 HTTP 409？
- [ ] **爭議工單權限**：爭議發起是否嚴格限制為該訂單之出借人或借用人 (403 Forbidden)？
- [ ] **防範注入**：SQL 查詢是否全數採用 SQLAlchemy ORM 參數化防護？

---

## 三、 PR 合併標準與回歸測試要求

在核准 (Approve) 並合併程式碼前，提交者必須證明以下三項檢驗通過：

1. **單元與整合測試**：
   ```powershell
   pytest tests -v
   ```
   👉 **51 / 51 項測試 100% 全數通過**。
2. **前端編譯**：
   ```powershell
   cd frontend; npm run build
   ```
   👉 **TypeScript 0 錯誤編譯成功**。
3. **UX 流程自動檢驗**：
   ```powershell
   python scripts/ux_check_runner.py
   ```
   👉 **六大分頁全流程 100% PASS**。

---

## 四、 常見審查駁回範例 (Anti-Patterns to Reject)

```python
# ❌ 駁回範例 1: 違反 Fail-Closed 原則 (預設放行)
if "error" not in result:
    return {"is_same_object": True}  # 危險！遇到未知狀況直接放行

# ✅ 修正範例 1: 嚴格落實 Fail-Closed
if not result or not result.get("is_same_object"):
    return {"is_same_object": False, "requires_retake": True}

# ❌ 駁回範例 2: 違反金融微文案合規 (出現特許違規詞)
return {"message": "損壞部分已由平台保險理賠。"}

# ✅ 修正範例 2: 合規法定文案
return {"message": "損壞超出押金部分已由社區互助保障池撥付責任補貼。"}
```
