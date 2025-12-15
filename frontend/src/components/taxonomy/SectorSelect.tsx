import React from 'react'

interface SectorSelectProps {
    value: string
    onChange: (value: string) => void
    sectors: string[]
    disabled?: boolean
    isLoading?: boolean
}

export default function SectorSelect({
    value,
    onChange,
    sectors,
    disabled = false,
    isLoading = false
}: SectorSelectProps) {
    return (
        <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
                Selecione o Setor
            </label>
            <select
                value={value}
                onChange={(e) => onChange(e.target.value)}
                className="w-full border border-gray-200 bg-white rounded-xl px-4 py-3 text-base text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 transition-all shadow-sm"
                disabled={disabled || isLoading}
            >
                {isLoading ? (
                    <option>Carregando setores...</option>
                ) : (
                    sectors.map((s) => (
                        <option key={s} value={s}>{s}</option>
                    ))
                )}
            </select>
        </div>
    )
}
