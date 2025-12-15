/**
 * Design Tokens - Strategic Control Tower Theme
 * 
 * A modern, clean, technological design system for Spend Analysis.
 * Inspired by corporate trust and control tower aesthetics.
 */

// ============================================
// STRATEGIC CONTROL TOWER PALETTE
// ============================================

export const colors = {
    // Primary - Deep Navy Blue (Corporate Trust)
    navy: {
        50: '#f0f4f8',
        100: '#d9e2ec',
        200: '#bcccdc',
        300: '#9fb3c8',
        400: '#829ab1',
        500: '#627d98',
        600: '#486581',
        700: '#334e68',
        800: '#243b53',
        900: '#102a43',  // Primary sidebar/buttons
    },

    // Accent - Electric Cyan (AI/Active states)
    cyan: {
        50: '#e0fcff',
        100: '#bef8fd',
        200: '#87eaf2',
        300: '#54d1db',
        400: '#38bec9',
        500: '#14919b',  // Primary accent
        600: '#0e7c86',
        700: '#0a6c74',
        800: '#084c61',
        900: '#044e54',
    },

    // Background
    background: {
        primary: '#F5F7FA',      // Off-white main area
        secondary: '#EDF2F7',    // Slightly darker sections
        card: '#FFFFFF',         // White floating cards
        sidebar: '#102a43',      // Deep Navy sidebar
        sidebarHover: '#1a3a54', // Sidebar item hover
    },

    // Text
    text: {
        primary: '#102a43',      // Navy for headings
        secondary: '#486581',    // Muted for body
        light: '#829ab1',        // Light gray
        white: '#FFFFFF',
        muted: '#9fb3c8',
    },

    // Status Colors
    status: {
        success: '#0e7c86',      // Cyan for success
        warning: '#f0b429',
        error: '#e12d39',
        info: '#2186eb',
    },

    // Legacy Brand (for logo compatibility)
    brand: {
        blue: '#1B75BB',
        turquoise: '#00A99D',
    },

    // Grays
    gray: {
        50: '#f9fafb',
        100: '#f3f4f6',
        200: '#e5e7eb',
        300: '#d1d5db',
        400: '#9ca3af',
        500: '#6b7280',
        600: '#4b5563',
        700: '#374151',
        800: '#1f2937',
        900: '#111827',
    }
} as const

// ============================================
// GRADIENTS
// ============================================

export const gradients = {
    // Primary navy gradient
    navy: 'from-[#102a43] to-[#243b53]',
    navyReverse: 'from-[#243b53] to-[#102a43]',

    // Cyan accent gradient
    cyan: 'from-[#14919b] to-[#38bec9]',
    cyanSubtle: 'from-[#14919b]/10 to-[#38bec9]/10',

    // Legacy brand gradient (for compatibility)
    brand: 'from-[#1B75BB] to-[#00A99D]',

    // Sidebar gradient
    sidebar: 'from-[#102a43] to-[#0d2136]',
} as const

// ============================================
// SHADOWS
// ============================================

export const shadows = {
    // Card shadows (soft, professional)
    sm: '0 1px 3px rgba(16, 42, 67, 0.08)',
    md: '0 4px 12px rgba(16, 42, 67, 0.10)',
    lg: '0 8px 24px rgba(16, 42, 67, 0.12)',
    xl: '0 12px 40px rgba(16, 42, 67, 0.15)',

    // Floating card shadow (for main content)
    card: '0 4px 20px rgba(16, 42, 67, 0.08)',

    // Input spotlight shadow
    input: '0 2px 8px rgba(16, 42, 67, 0.06)',
    inputFocus: '0 0 0 3px rgba(20, 145, 155, 0.15)',

    // Cyan glow for AI states
    glow: '0 0 20px rgba(20, 145, 155, 0.4)',
    glowSubtle: '0 0 12px rgba(20, 145, 155, 0.2)',
} as const

// ============================================
// TAILWIND CLASS COMBINATIONS
// ============================================

export const tw = {
    // Glassmorphism effects
    glass: 'bg-white/80 backdrop-blur-sm border border-white/50',
    glassStrong: 'bg-white/95 backdrop-blur-xl border border-gray-100',
    glassDark: 'bg-[#102a43]/80 backdrop-blur-sm border border-white/10',

    // Gradient text
    gradientText: 'bg-gradient-to-r from-[#14919b] to-[#38bec9] bg-clip-text text-transparent',
    navyText: 'text-[#102a43]',

    // Button variants - Navy primary
    buttonPrimary: 'bg-[#102a43] text-white hover:bg-[#243b53] transition-all duration-200 shadow-md hover:shadow-lg',
    buttonCyan: 'bg-gradient-to-r from-[#14919b] to-[#38bec9] text-white hover:shadow-lg transition-all duration-200',
    buttonSecondary: 'bg-white border border-gray-200 text-[#486581] hover:bg-gray-50 hover:border-gray-300 transition-colors',
    buttonGhost: 'text-[#486581] hover:text-[#102a43] hover:bg-gray-100 transition-colors',

    // Card styles - Floating white cards
    card: 'bg-white rounded-2xl shadow-[0_4px_20px_rgba(16,42,67,0.08)] border border-gray-100',
    cardHover: 'hover:shadow-[0_8px_30px_rgba(16,42,67,0.12)] hover:translate-y-[-2px] transition-all duration-300',

    // Sidebar styles
    sidebarItem: 'text-white/70 hover:text-white hover:bg-white/10 transition-all duration-200',
    sidebarItemActive: 'text-white bg-white/15 backdrop-blur-sm border-l-2 border-[#38bec9]',

    // Input styles - Spotlight style
    input: 'w-full px-4 py-3 rounded-xl border border-gray-200 bg-white shadow-[0_2px_8px_rgba(16,42,67,0.06)] focus:outline-none focus:ring-2 focus:ring-[#14919b]/20 focus:border-[#14919b] focus:shadow-[0_0_0_3px_rgba(20,145,155,0.15)] transition-all',
    inputFloating: 'bg-white rounded-2xl shadow-[0_4px_20px_rgba(16,42,67,0.10)] border border-gray-100 p-3',

    // Animation classes
    pulseGlow: 'animate-pulse shadow-[0_0_20px_rgba(20,145,155,0.4)]',
    fadeIn: 'animate-[fadeIn_0.5s_ease-out_forwards]',
    slideUp: 'animate-[slideUp_0.3s_ease-out_forwards]',
} as const

// ============================================
// ICON COLORS
// ============================================

export const iconColors = {
    navy: 'text-[#102a43]',
    cyan: 'text-[#14919b]',
    muted: 'text-[#829ab1]',
    white: 'text-white',
    success: 'text-[#0e7c86]',
    warning: 'text-amber-500',
    error: 'text-red-500',
} as const

// ============================================
// TYPOGRAPHY
// ============================================

export const typography = {
    fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    heading: 'font-semibold text-[#102a43]',
    body: 'text-[#486581]',
    caption: 'text-sm text-[#829ab1]',
} as const

export default {
    colors,
    gradients,
    shadows,
    tw,
    iconColors,
    typography,
}
