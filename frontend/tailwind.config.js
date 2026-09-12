/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        diyYellow: {
          50: '#FFFBED',
          100: '#FFF8D6',
          200: '#FFF0AD',
          300: '#FFE680',
          400: '#FFD833',
          500: '#FFD000', // MR. DIY 標誌性鮮黃 (主品牌色 Primary Brand)
          600: '#E6BC00', // Hover 壓深
          700: '#B39200',
          800: '#806800',
          900: '#4D3E00',
        },
        diyDark: {
          DEFAULT: '#1A1A1A',     // 高對比工業黑
          500: '#2A2A2E',
          600: '#252528',
          700: '#1F1F23',
          800: '#18181B',
          900: '#121214',
        },
        brandDark: '#0E0E10',   // 次深黑底色
        brandGray: {
          50: '#F9FAFB',
          100: '#F3F4F6',
          200: '#E5E7EB',
          300: '#D1D5DB',
          400: '#9CA3AF',
          500: '#6B7280',
          600: '#4B5563',
          700: '#374151',
          800: '#1F2937',
          900: '#111827',
        },
        // 語意狀態色 (Semantic Colors)
        diySuccess: '#16A34A',  // 驗證通過、檢查無損
        diyWarning: '#F59E0B',  // 微幅異動 (MINOR_DIFF)、注意警告
        diyDanger: '#DC2626',   // 嚴重損壞 (DAMAGE_DETECTED)、爭議凍結
        diyInfo: '#2563EB',     // 狸利系統提示
      },
      boxShadow: {
        'glow-yellow': '0 0 20px rgba(255, 208, 0, 0.45)',
        'glow-yellow-sm': '0 0 10px rgba(255, 208, 0, 0.3)',
      },
      borderRadius: {
        '2xl': '1rem',
        '3xl': '1.5rem',
      },
      fontFamily: {
        sans: [
          '-apple-system',
          'BlinkMacSystemFont',
          '"Noto Sans TC"',
          '"PingFang TC"',
          '"Microsoft JhengHei"',
          'sans-serif',
        ],
      },
    },
  },
  plugins: [],
};
