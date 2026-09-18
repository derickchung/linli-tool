import React from 'react';
import { PrimaryCTAButton } from './PrimaryCTAButton';

export interface PreAuthCardProps {
  toolName: string;
  dailyRate: number;
  rentDays: number;
  totalRent: number;
  baseDeposit: number;
  actualDeposit: number;
  authorizedTotal: number;
  creditScore: number;
  poolCoverageApplicable?: boolean;
  onConfirm?: () => void;
  loading?: boolean;
  className?: string;
}

export const PreAuthCard: React.FC<PreAuthCardProps> = ({
  toolName,
  dailyRate,
  rentDays,
  totalRent,
  baseDeposit,
  actualDeposit,
  authorizedTotal,
  creditScore,
  poolCoverageApplicable = true,
  onConfirm,
  loading = false,
  className = '',
}) => {
  const depositDiscount = baseDeposit - actualDeposit;

  return (
    <div
      className={`bg-amber-50 border border-amber-200 rounded-2xl p-4 sm:p-5 text-diyDark shadow-sm ${className}`}
      data-testid="pre-auth-card"
    >
      <div className="flex items-center justify-between pb-2.5 border-b border-amber-200/80 mb-3">
        <h3 className="font-black text-lg text-diyDark">金流預授權試算明細</h3>
        {poolCoverageApplicable && (
          <span className="text-[11px] font-bold bg-amber-200/80 text-amber-900 px-2.5 py-0.5 rounded-full">
            平台互助保障支援
          </span>
        )}
      </div>

      <div className="space-y-2.5 text-sm mb-4">
        {/* 租金拆解 */}
        <div className="flex justify-between items-center">
          <span className="text-gray-600">工具總租金 ({dailyRate} 元 × {rentDays} 天)</span>
          <span className="font-bold text-base">NT$ {totalRent}</span>
        </div>

        {/* 履約押金 */}
        <div className="flex justify-between items-center">
          <span className="text-gray-600">履約押金 (基準 NT$ {baseDeposit})</span>
          <div className="text-right">
            {depositDiscount > 0 ? (
              <>
                <span className="line-through text-gray-400 text-xs mr-1.5">NT$ {baseDeposit}</span>
                <span className="font-bold text-green-700">NT$ {actualDeposit}</span>
              </>
            ) : (
              <span className="font-bold">NT$ {actualDeposit}</span>
            )}
          </div>
        </div>

        {/* 信用分減免高亮 */}
        {depositDiscount > 0 && (
          <div className="flex justify-between items-center text-xs text-green-700 bg-green-100/70 px-2.5 py-1 rounded-lg">
            <span>🛡️ 信用守護獎勵 (信用分 {creditScore})</span>
            <span className="font-bold">減免 -NT$ {depositDiscount}</span>
          </div>
        )}
      </div>

      {/* 授權總額 */}
      <div className="pt-3 border-t border-amber-200/80 mb-4 flex justify-between items-baseline">
        <span className="font-bold text-gray-700">授權總額 (租金 + 押金)</span>
        <span className="text-2xl font-black text-diyDark">NT$ {authorizedTotal}</span>
      </div>

      {/* 預授權防慌張微文案提示 */}
      <div className="bg-white/80 p-2.5 sm:p-3 rounded-xl text-xs text-gray-600 mb-3 border border-amber-100 leading-relaxed">
        💡 <strong className="text-gray-800">預授權鎖定說明：</strong>
        系統僅先鎖定信用額度，絕非立即扣款。租期結束且雙方確認工具無損後，押金額度將即刻自動釋出。
      </div>

      {/* 主行動按鈕 */}
      <div className="pt-1">
        <PrimaryCTAButton
          fullWidth
          size="md"
          loading={loading}
          onClick={onConfirm}
          data-testid="pre-auth-confirm-button"
          className="text-xs sm:text-sm font-extrabold py-3.5 leading-snug"
        >
          發起預約並執行預授權鎖定 (歸還無誤即放行押金)
        </PrimaryCTAButton>
      </div>
    </div>
  );
};

export default PreAuthCard;
