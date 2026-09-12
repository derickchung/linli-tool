/**
 * LinLi Tool 微文案規範與 Anti-pattern 檢核表 (Microcopy Standards)
 * 依據 design_guide.md 4.4 節與 PRD 6.3 節規範
 */

export const FORBIDDEN_FINANCIAL_TERMS = [
  '保險',
  '保費',
  '理賠',
  '理賠金',
  '承保',
  '保單',
] as const;

export const MICROCOPY_STANDARDS = {
  PRE_AUTH: {
    title: '總租金 + 履約押金 = 授權總額',
    ctaButton: '發起預約並執行預授權鎖定 (歸還無誤即放行押金)',
    tip: '預授權僅先鎖定信用額度，租期結束且工具確認無誤後，押金即刻解除鎖定釋出。',
    antiPattern: '立即扣款 NT$ 732',
  },
  CAMERA_GUIDE: {
    checkinNotice: '請將工具置於引導框內，狸利會自動協助遮蔽住宅隱私。',
    markOldDamage: '拍攝並標註初始舊傷，保護您的借用權益。',
    antiPattern: '拍攝以確立免責聲明，違者後果自負',
  },
  CHECKOUT_DIFF: {
    minorDiffTip: '檢測到表面有微幅痕跡 (Diff: 0.18)，是否需補充清潔照或說明？',
    antiPattern: '檢測到損壞，準備扣除押金 NT$ 600',
  },
  COMPENSATION_POOL: {
    legalTerm: '平台損壞互助保障',
    payoutTerm: '互助保障補貼支出',
    antiPattern: '安心保險理賠',
  },
} as const;

/**
 * 檢查字串是否包含違規金融用語
 */
export function validateMicrocopy(text: string): { valid: boolean; violations: string[] } {
  const violations: string[] = [];
  for (const term of FORBIDDEN_FINANCIAL_TERMS) {
    if (text.includes(term)) {
      violations.push(term);
    }
  }
  return {
    valid: violations.length === 0,
    violations,
  };
}
