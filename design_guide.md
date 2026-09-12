# LinLi Tool (鄰里工具) 品牌視覺與設計系統指南

- **版本**：v1.0
- **專案**：LinLi Tool 鄰里工具 — 社區設備共享與信任機制平台
- **核心主題**：活力鮮黃 × 狸利 (LiLi) 海狸工程師 × 工業高對比現代質感

---

## 目錄

1. [品牌核心識別 (Brand Identity & Philosophy)](#1-品牌核心識別-brand-identity--philosophy)
2. [顏色系統與 Design Tokens (Color Palette)](#2-顏色系統與-design-tokens-color-palette)
3. [Typography & Font Hierarchy (字型與版型規範)](#3-typography--font-hierarchy-字型與版型規範)
4. [UI 元件與設計標記規範 (UI Design Tokens & Components)](#4-ui-元件與設計標記規範-ui-design-tokens--components)
5. [品牌語調與微文案規範 (Voice, Tone & Microcopy)](#5-品牌語調與微文案規範-voice-tone--microcopy)
6. [設計標記 Code Export (Tailwind CSS Config Extend)](#6-設計標記-code-export-tailwind-css-config-extend)

---

## 1. 品牌核心識別 (Brand Identity & Philosophy)

### 1.1 品牌名稱與標語
* **中文名稱**：鄰里工具 (LinLi Tool)
* **英文名稱**：LinLi Tool
* **品牌 Slogan**：社區設備共享，信任零距離 (Community Shared Tools, Trust at Your Doorstep)
* **品牌精神**：利用地緣便利性與微型信任機制，讓「低頻剛需」的居家工具在社區內循環流動，減少囤積與浪費，創造鄰里共好與永續生活。

### 1.2 吉祥物角色規格 (Mascot Identity)
* **角色名稱**：狸利 (LiLi)
* **物種**：海狸 (Beaver) —— 象徵「自然界最優秀的土木工程師、勤勞築巢、最擅長使用工具與組裝構造物」。
* **外貌特徵**：
  1. **標誌配件**：頭戴 MR. DIY 風格活力鮮黃安全帽，正面標有「LiLi」黑底黃字工安標章。
  2. **穿著風格**：深灰/黑色工裝背心與雙門牙可愛笑臉，腰帶掛有電鑽與扳手。
* **角色性格**：熱情鄰家、注重安全、嚴謹細緻、值得信任。
* **頭身比例**：2.5 頭身 Q 版造型，兼具科技感與親和力。
* **吉祥物應用場景 (Mascot Moods)**：
  1. **迎賓導覽 (Friendly Greeter)**：手持工具向住戶打招呼（首頁 Banner、早安問候）。
  2. **AI 相機助手 (Vigilant Inspector)**：戴著放大鏡或相機提示拍攝對齊與光線補償（取還拍照、瑕疵辨識畫面）。
  3. **信用守護者 (Trust Guardian)**：手持盾牌與維修工具（信用分數與保障金模組）。
  4. **物業值班員 (Gatekeeper LiLi)**：戴著工作識別證協助保全清點配件（物業管理交接端）。

---

## 2. 顏色系統與 Design Tokens (Color Palette)

品牌色彩設計以 **MR. DIY 代表性的高能活力鮮黃** 為主視覺，搭配 **深炭灰黑 (DIY Dark Charcoal)** 形成強烈專業工業風格，並導入極具辨識度的功能狀態色。

### 2.1 主色系 (Brand Core Colors)

| 色彩名稱 | HEX Code | Tailwind Class / RGB | 應用場景 |
|---|---|---|---|
| **DIY Vibrant Yellow (品牌主黃)** | `#FFC801` | `bg-diyYellow-500` / `rgb(255, 200, 1)` | 品牌 Primary 按鈕、吉祥物帽子、主 Banner、重點 Highlight |
| **Bright Gold (亮金黃)** | `#FFD700` | `bg-diyYellow-400` / `rgb(255, 215, 0)` | Hover 狀態、黃色發光 Glow 效果、懸浮標章 |
| **Dark Gold (深金黃)** | `#E6A800` | `text-diyYellow-600` / `rgb(230, 168, 0)` | 深色背景上的文字、圖示主色、邊框聚焦線 |
| **DIY Industrial Dark (工業深炭灰)** | `#1E1E24` | `bg-diyDark` / `rgb(30, 30, 36)` | 頁首 Global Header、手機模擬框、高對比 Card 卡片 |
| **Brand Jet Black (純粹黑)** | `#18181B` | `bg-brandDark` / `rgb(24, 24, 27)` | 頁尾 Footer、Modal 遮罩、高階相機 Viewfinder 背景 |

### 2.2 輔助與中性色系 (Neutral & Background Colors)

| 色彩名稱 | HEX Code | 應用場景 |
|---|---|---|
| **App Canvas BG** | `#F3F4F6` | 全站主要背景底色 (Light Mode Slate-100) |
| **Card Surface White** | `#FFFFFF` | 主要卡片與元件背景色 |
| **Muted Border Slate** | `#E2E8F0` | 卡片細線邊框 (Slate-200) |
| **Subtle Text Slate** | `#64748B` | 次要說明文字、時間標籤 (Slate-500) |
| **Primary Text Charcoal** | `#0F172A` | 主要內文標題 (Slate-900) |

### 2.3 功能狀態色系 (Functional Status Colors)

| 狀態名稱 | HEX Code | 語意與應用場景 |
|---|---|---|
| **Success Emerald (成功/可借用)** | `#10B981` | 工具「可立即借用」、押金「解鎖順利結案」、信用分加分 |
| **Warning Amber (警告/預授權)** | `#D97706` | 「金額預授權鎖定中」、Ghost 比對「出現微幅差異」、逾期提醒 |
| **Danger Ruby (危險/爭議/損壞)** | `#EF4444` | AI 檢測「新痕跡/刮傷」、帳號「停權」、爭議仲裁扣款 |
| **Info Sapphire (資訊/品牌贊助)** | `#3B82F6` | 「Bosch 品牌贊助」標籤、無接觸物業架位指引 (A-02架) |

---

## 3. Typography & Font Hierarchy (字型與版型規範)

字體選擇兼具高科技數位感與中文字型易讀性，確保在 Mobile 手機端與 Admin Web 儀表板皆有優異的閱讀體驗。

### 3.1 字型家族 (Font Family)
* **英數字型**：`Inter`, `apple-system`, `BlinkMacSystemFont`
* **中文字型**：`Noto Sans TC` (思源黑體), `Microsoft JhengHei`
* **CSS Font Stack**：`font-family: 'Inter', 'Noto Sans TC', sans-serif;`

### 3.2 字級與字重規範 (Type Scale)

| 層級 | 字級 (Font Size) | 字重 (Weight) | Tailwind Class | 應用範例 |
|---|---|---|---|---|
| **Display Header** | 24px / 1.5rem | Black (900) | `text-2xl font-black` | 手機版頂部標題、促銷金額 |
| **H1 Title** | 20px / 1.25rem | Bold (700) | `text-xl font-bold` | 工具名稱、Modal 大標題 |
| **H2 Section Title** | 16px / 1.0rem | Bold (700) | `text-base font-bold` | 區塊標題、配件清單標題 |
| **Body Primary** | 14px / 0.875rem | Regular (400) / Medium (500) | `text-sm font-normal` | 主要說明文案、預約細節 |
| **Body Secondary** | 12px / 0.75rem | Regular (400) | `text-xs text-gray-500` | 時間戳記、次要提示、地址標籤 |
| **Micro Caption/Badge** | 10px / 0.625rem | Black (900) / Bold (700) | `text-[10px] font-bold` | 分類 Badge、信用分膠囊標籤 |

---

## 4. UI 元件與設計標記規範 (UI Design Tokens & Components)

### 4.1 圓角系統 (Corner Radius)
* **App Phone Inner Containers**：`28px` (`rounded-[28px]`)
* **Cards & Major Modals**：`16px` 或 `24px` (`rounded-2xl` / `rounded-3xl`)
* **Buttons & Inputs**：`12px` (`rounded-xl`)
* **Badges & Status Tags**：`9999px` (`rounded-full`)

### 4.2 光影與質感 (Shadows & Elevation)
* **Subtle Card Shadow**：`shadow-xs` (`0 1px 2px 0 rgba(0, 0, 0, 0.05)`)
* **Interactive Hover Shadow**：`shadow-md` (`0 4px 6px -1px rgba(0, 0, 0, 0.1)`)
* **Yellow Brand Glow (品牌黃光效果)**：
  ```css
  .glow-yellow {
    box-shadow: 0 0 20px rgba(255, 200, 1, 0.4);
  }
  ```

### 4.3 核心 UI 元件庫語言 (Key UI Component Patterns)

#### 1. 信用分數徽章 (Credit Score Badge)
* **外觀**：深灰底黑色膠囊，金黃色邊框與金黃盾牌 Icon。
* **代碼樣式**：
  ```html
  <div class="bg-diyDark text-white px-2.5 py-1 rounded-full text-xs font-bold border border-diyYellow-500">
    <!-- Icon + 信用分數 -->
  </div>
  ```

#### 2. 主行動按鈕 (Primary CTA Button)
* **外觀**：MR. DIY 亮黃底色、深炭灰粗體文字、圓角 12px，滑鼠 Hover 時微幅亮化。
* **代碼樣式**：
  ```html
  <button class="bg-diyYellow-500 hover:bg-diyYellow-600 text-diyDark font-black py-3 px-4 rounded-xl shadow-md transition-all">
    發起預約並簽署
  </button>
  ```

#### 3. Ghost Overlay 比對視窗 (Camera Alignment Viewfinder)
* **外觀**：深色 4:3 比例預覽框、鮮黃虛線對齊引導框、30% 半透明層。
* **代碼樣式**：
  ```html
  <div class="border-2 border-dashed border-diyYellow-500 opacity-35">
    <!-- 鏡頭引導虛線框 -->
  </div>
  ```

#### 4. 金流預授權計算卡片 (Pre-authorization Breakdown Card)
* **外觀**：淺黃底色 (`bg-amber-50`)，深黃細邊框 (`border-amber-200`)，以清晰明瞭的列明表格呈現「租金 + 保障金 + 履約押金 = 授權總額」。

---

## 5. 品牌語調與微文案規範 (Voice, Tone & Microcopy)

### 5.1 語調原則 (Brand Voice Principles)
1. **鄰家親切 (Neighborly & Approachable)**：使用「早安！」、「狸利提示」等溫暖口吻，降低工具修繕的硬核門檻。
2. **透明透明再透明 (Radically Transparent)**：在扣款與押金授權處，永遠明確標註「歸還無誤即放行預授權」，消解借用人資金疑慮。
3. **安全專業 (Safety & Reassuring)**：強調「平台安心保障金」、「3秒去識別化模糊」，展現科技與法律保障。

### 5.2 微文案標準範例 (Microcopy Examples)

| 情境 (Scenario) | 推薦微文案 (Recommended Microcopy) | 避免文案 (Anti-pattern) |
|---|---|---|
| **金流預授權** | 「發起預約並執行預授權鎖定 (歸還無誤即放行押金)」 | 「立即扣款 NT$ 732」 |
| **AI 相機拍攝** | 「請將工具置於引導框內，狸利會自動協助遮蔽住宅隱私」 | 「上傳照片進行掃描」 |
| **舊傷標註** | 「拍攝並標註初始舊傷，保護您的借用權益」 | 「舊傷免責聲明」 |
| **AI 檢測到異動** | 「檢測到表面有微幅痕跡 (Diff: 0.18)，是否需補充清潔照或說明？」 | 「檢測到損壞，準備扣除押金」 |

---

## 6. 設計標記 Code Export (Tailwind CSS Config Extend)

可以直接將以下設定融入前端專案之 `tailwind.config.js` 中：

```javascript
module.exports = {
  theme: {
    extend: {
      colors: {
        diyYellow: {
          400: '#FFD700',
          500: '#FFC801', // MR. DIY Primary Yellow
          600: '#E6A800',
          700: '#C28B00',
        },
        diyDark: '#1E1E24',
        brandDark: '#18181B',
      },
      fontFamily: {
        sans: ['Inter', 'Noto Sans TC', 'sans-serif'],
      },
      borderRadius: {
        'xl': '12px',
        '2xl': '16px',
        '3xl': '24px',
        'phone': '28px',
      },
      boxShadow: {
        'glow-yellow': '0 0 20px rgba(255, 200, 1, 0.4)',
      },
    },
  },
};
```
