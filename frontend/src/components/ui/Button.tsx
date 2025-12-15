import React from 'react'
import { tw } from '@/lib/design-tokens'

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
    variant?: 'primary' | 'secondary' | 'ghost'
    size?: 'sm' | 'md' | 'lg'
    loading?: boolean
    icon?: React.ReactNode
    children: React.ReactNode
}

const sizeMap = {
    sm: 'px-3 py-1.5 text-sm',
    md: 'px-4 py-2 text-sm',
    lg: 'px-6 py-3 text-base',
}

const variantMap = {
    primary: tw.buttonPrimary,
    secondary: tw.buttonSecondary,
    ghost: tw.buttonGhost,
}

export default function Button({
    variant = 'primary',
    size = 'md',
    loading = false,
    icon,
    children,
    className = '',
    disabled,
    ...props
}: ButtonProps) {
    return (
        <button
            className={`
        inline-flex items-center justify-center gap-2 rounded-lg font-medium
        ${variantMap[variant]}
        ${sizeMap[size]}
        ${disabled || loading ? 'opacity-50 cursor-not-allowed' : ''}
        ${className}
      `}
            disabled={disabled || loading}
            {...props}
        >
            {loading ? (
                <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
            ) : icon ? (
                icon
            ) : null}
            {children}
        </button>
    )
}
