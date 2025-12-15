import React from 'react'
import { tw } from '@/lib/design-tokens'

interface CardProps {
    children: React.ReactNode
    className?: string
    variant?: 'default' | 'glass' | 'glassStrong'
    hover?: boolean
    padding?: 'none' | 'sm' | 'md' | 'lg'
}

const paddingMap = {
    none: '',
    sm: 'p-4',
    md: 'p-6',
    lg: 'p-8',
}

const variantMap = {
    default: 'bg-white rounded-2xl border border-gray-100 shadow-sm',
    glass: tw.glass + ' rounded-2xl shadow-sm',
    glassStrong: tw.glassStrong + ' rounded-2xl shadow-xl',
}

export default function Card({
    children,
    className = '',
    variant = 'default',
    hover = false,
    padding = 'md'
}: CardProps) {
    return (
        <div
            className={`
        ${variantMap[variant]}
        ${paddingMap[padding]}
        ${hover ? tw.cardHover : ''}
        ${className}
      `}
        >
            {children}
        </div>
    )
}
