import React from 'react';

export interface CreditScoreBadgeProps {
  score: number;
  showTierText?: boolean;
  className?: string;
}

export const CreditScoreBadge: React.FC<CreditScoreBadgeProps> = ({
  score,
  showTierText = true,
  className = '',
}) => {
  let tierLabel = '全額押金';
  let tierColor = 'text-gray-300';
  let badgeBorder = 'border-gray-600';

  if (score >= 100) {
    tierLabel = '信用極佳・免押金 (0%)';
    tierColor = 'text-diyYellow-400';
    badgeBorder = 'border-diyYellow-500';
  } else if (score >= 80) {
    tierLabel = '信用良好・押金半價 (50%)';
    tierColor = 'text-yellow-200';
    badgeBorder = 'border-yellow-400';
  } else {
    tierLabel = '一般住戶・標準押金 (100%)';
    tierColor = 'text-gray-300';
    badgeBorder = 'border-gray-500';
  }

  return (
    <div
      className={`inline-flex items-center gap-1.5 bg-diyDark text-white px-3 py-1 rounded-full text-xs font-bold border ${badgeBorder} shadow-sm ${className}`}
      data-testid="credit-score-badge"
    >
      <span className="text-diyYellow-500 text-sm font-black" role="img" aria-label="trust-guardian">
        🛡️
      </span>
      <span>信用分 {score}</span>
      {showTierText && (
        <>
          <span className="text-gray-500">|</span>
          <span className={`${tierColor} font-normal`}>{tierLabel}</span>
        </>
      )}
    </div>
  );
};

export default CreditScoreBadge;
