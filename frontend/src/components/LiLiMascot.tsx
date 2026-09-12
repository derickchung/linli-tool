import React from 'react';

export type LiLiRole = 'FriendlyGreeter' | 'VigilantInspector' | 'TrustGuardian' | 'PropertyAttendant';

export interface LiLiMascotProps {
  role: LiLiRole;
  message?: string;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const ROLE_ICONS: Record<LiLiRole, { emoji: string; title: string; defaultMsg: string }> = {
  FriendlyGreeter: {
    emoji: '👋🦫',
    title: '迎賓導覽狸利',
    defaultMsg: '早安！我是鄰里工具工程師狸利，今天想租借什麼工具完成居家修繕呢？',
  },
  VigilantInspector: {
    emoji: '🔍🦫',
    title: 'AI 相機助手狸利',
    defaultMsg: '請將工具置於引導框內，狸利會自動協助遮蔽住宅隱私，並標註初始舊傷維護您的權益！',
  },
  TrustGuardian: {
    emoji: '🛡️🦫',
    title: '信用守護者狸利',
    defaultMsg: '恭喜您累積優質信用！信用評分可享有押金折抵減免優惠喔！',
  },
  PropertyAttendant: {
    emoji: '🏢🦫',
    title: '物業值班員狸利',
    defaultMsg: '管理室已準備好安全交接工具，請出示 6 碼動態核銷碼給出借鄰居確認。',
  },
};

export const LiLiMascot: React.FC<LiLiMascotProps> = ({
  role,
  message,
  size = 'md',
  className = '',
}) => {
  const meta = ROLE_ICONS[role];
  const displayMsg = message || meta.defaultMsg;

  const sizeClasses = {
    sm: 'text-base p-2.5 text-xs',
    md: 'text-xl p-3.5 text-sm',
    lg: 'text-3xl p-5 text-base',
  }[size];

  return (
    <div
      className={`inline-flex items-center gap-3 bg-white/90 border border-diyYellow-400/60 rounded-2xl shadow-sm text-diyDark ${sizeClasses} ${className}`}
      data-testid={`lili-mascot-${role.toLowerCase()}`}
    >
      <span className="shrink-0 select-none" role="img" aria-label={meta.title}>
        {meta.emoji}
      </span>
      <div className="flex flex-col text-left">
        <span className="font-bold text-[11px] text-yellow-700 tracking-wider uppercase">
          {meta.title}
        </span>
        <span className="font-medium text-gray-700 leading-snug">{displayMsg}</span>
      </div>
    </div>
  );
};

export default LiLiMascot;
