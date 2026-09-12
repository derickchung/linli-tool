export interface GhostOverlayViewfinderProps {
  mode: 'checkin' | 'checkout';
  overlayImageUrl?: string;
  capturedImageUrl?: string;
  onCapture?: () => void;
  className?: string;
}

export const GhostOverlayViewfinder: React.FC<GhostOverlayViewfinderProps> = ({
  mode,
  overlayImageUrl,
  capturedImageUrl,
  onCapture,
  className = '',
}) => {
  return (
    <div
      className={`relative w-full max-w-md mx-auto aspect-[4/3] rounded-2xl overflow-hidden bg-black flex flex-col items-center justify-center ${className}`}
      data-testid="ghost-overlay-viewfinder"
    >
      {/* 歸還現場實拍相片 (底層) */}
      {capturedImageUrl && (
        <img
          src={capturedImageUrl}
          alt="現場實拍相片"
          className="absolute inset-0 w-full h-full object-cover z-0"
        />
      )}

      {/* 4:3 鮮黃虛線對齊引導框 */}
      <div className="absolute inset-4 rounded-xl border-2 border-dashed border-diyYellow-500 pointer-events-none z-20 flex flex-col justify-between p-3">
        <div className="flex justify-between items-center text-[10px] text-diyYellow-400 bg-black/60 px-2 py-0.5 rounded backdrop-blur-sm self-start">
          <span>{mode === 'checkin' ? '📸 Check-in 存證模式' : '🔄 Check-out 同視角比對'}</span>
        </div>

        {/* 4 角強化對齊準星 */}
        <div className="absolute top-2 left-2 w-4 h-4 border-t-2 border-l-2 border-diyYellow-500" />
        <div className="absolute top-2 right-2 w-4 h-4 border-t-2 border-r-2 border-diyYellow-500" />
        <div className="absolute bottom-2 left-2 w-4 h-4 border-b-2 border-l-2 border-diyYellow-500" />
        <div className="absolute bottom-2 right-2 w-4 h-4 border-b-2 border-r-2 border-diyYellow-500" />
      </div>

      {/* Ghost Overlay 舊照半透明層 (歸還模式疊印，opacity 0.35) */}
      {mode === 'checkout' && overlayImageUrl && (
        <img
          src={overlayImageUrl}
          alt="Ghost Overlay 初始存證輪廓"
          className="absolute inset-0 w-full h-full object-contain pointer-events-none z-10 opacity-35 filter contrast-125"
          data-testid="ghost-overlay-layer"
        />
      )}


      {/* AI 相機助手狸利溫和引導微文案 */}
      <div className="absolute bottom-6 inset-x-6 z-30 bg-diyDark/85 text-white text-xs p-2.5 rounded-xl border border-diyYellow-500/40 backdrop-blur-sm flex items-center gap-2">
        <span className="text-lg" role="img" aria-label="inspector-lili">
          🔍
        </span>
        <p className="leading-relaxed">
          {mode === 'checkin'
            ? '請將工具置於引導框內，狸利會自動協助遮蔽住宅隱私。拍攝並標註初始舊傷，保護您的借用權益。'
            : '已疊加取件時的存證輪廓 (35% 半透明)，請對齊角度拍攝，微幅灰塵木屑不會計入損壞喔！'}
        </p>
      </div>
    </div>
  );
};

export default GhostOverlayViewfinder;
