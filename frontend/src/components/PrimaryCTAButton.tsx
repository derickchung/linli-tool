import React from 'react';

export interface PrimaryCTAButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  loading?: boolean;
  fullWidth?: boolean;
  size?: 'sm' | 'md' | 'lg';
  children: React.ReactNode;
}

export const PrimaryCTAButton: React.FC<PrimaryCTAButtonProps> = ({
  loading = false,
  fullWidth = false,
  size = 'lg',
  children,
  className = '',
  disabled,
  ...props
}) => {
  const sizeClasses = {
    sm: 'px-3 py-1.5 text-xs rounded-xl',
    md: 'px-4 py-2.5 text-sm rounded-xl',
    lg: 'px-6 py-3.5 text-base rounded-2xl',
  };

  return (
    <button
      className={`
        relative inline-flex items-center justify-center font-black
        bg-diyYellow-500 hover:bg-diyYellow-600 active:scale-[0.98]
        text-diyDark
        shadow-glow-yellow transition-all duration-150
        disabled:opacity-50 disabled:cursor-not-allowed disabled:shadow-none
        ${sizeClasses[size]}
        ${fullWidth ? 'w-full' : ''}
        ${className}
      `}
      disabled={disabled || loading}
      data-testid="primary-cta-button"
      {...props}
    >
      {loading ? (
        <span className="inline-flex items-center gap-2">
          <svg className="animate-spin h-5 w-5 text-diyDark" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
          </svg>
          處理中...
        </span>
      ) : (
        children
      )}
    </button>
  );
};

export default PrimaryCTAButton;
