import React from 'react'
import { tw } from '@/lib/design-tokens'

interface TabItem {
    id: string
    label: string
}

interface TabsProps {
    tabs: TabItem[]
    activeTab: string
    onTabChange: (tabId: string) => void
    disabled?: boolean
}

export default function Tabs({ tabs, activeTab, onTabChange, disabled }: TabsProps) {
    return (
        <div className="grid grid-cols-3 gap-1 w-full p-1.5 bg-white rounded-xl border border-gray-200 shadow-sm">
            {tabs.map((tab) => (
                <button
                    key={tab.id}
                    onClick={() => !disabled && onTabChange(tab.id)}
                    disabled={disabled}
                    className={`
                        relative py-3 px-2 text-sm font-medium transition-all duration-300 rounded-lg text-center
                        ${activeTab === tab.id
                            ? 'text-white bg-gradient-to-r from-[#1c0957] to-[#2a1177] shadow-md'
                            : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100'
                        }
                        ${disabled ? 'cursor-not-allowed opacity-50' : ''}
                    `}
                >
                    <span className="truncate block w-full">{tab.label}</span>
                    {activeTab === tab.id && (
                        <div className="absolute bottom-0 left-1/4 right-1/4 h-0.5 bg-[#38bec9] rounded-full" />
                    )}
                </button>
            ))}
        </div>
    )
}
