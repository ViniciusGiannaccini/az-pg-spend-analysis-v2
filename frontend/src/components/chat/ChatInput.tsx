import React from 'react'

interface ChatInputProps {
    value: string
    onChange: (value: string) => void
    onSend: () => void
    disabled?: boolean
    loading?: boolean
    placeholder?: string
}

export default function ChatInput({
    value,
    onChange,
    onSend,
    disabled = false,
    loading = false,
    placeholder = 'Faça uma pergunta sobre a análise...'
}: ChatInputProps) {
    const handleKeyPress = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey && !disabled && !loading && value.trim()) {
            e.preventDefault()
            onSend()
        }
    }

    return (
        <div className="input-spotlight p-3">
            <div className="flex items-center gap-3">
                {/* Input Field */}
                <div className="flex-1 relative">
                    <input
                        type="text"
                        value={value}
                        onChange={(e) => onChange(e.target.value)}
                        onKeyPress={handleKeyPress}
                        placeholder={loading ? 'Processando...' : placeholder}
                        disabled={disabled || loading}
                        className="w-full px-4 py-3 bg-[#F5F7FA] rounded-xl border-0 text-[#102a43] placeholder-[#829ab1] focus:outline-none focus:ring-2 focus:ring-[#14919b]/20 disabled:opacity-50 disabled:cursor-not-allowed transition-all text-sm"
                    />

                    {/* AI Indicator */}
                    <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-2">
                        {loading && (
                            <div className="flex gap-1">
                                <div className="w-1.5 h-1.5 bg-[#14919b] rounded-full animate-thinking"></div>
                                <div className="w-1.5 h-1.5 bg-[#14919b] rounded-full animate-thinking delay-200"></div>
                                <div className="w-1.5 h-1.5 bg-[#14919b] rounded-full animate-thinking delay-300"></div>
                            </div>
                        )}
                    </div>
                </div>

                {/* Send Button - Teal Gradient */}
                <button
                    onClick={onSend}
                    disabled={disabled || loading || !value.trim()}
                    className="px-5 py-3 bg-gradient-to-r from-[#38bec9] to-[#14919b] hover:from-[#4dd0d9] hover:to-[#38bec9] text-white rounded-xl font-medium text-sm transition-all duration-200 disabled:opacity-40 disabled:cursor-not-allowed disabled:from-gray-400 disabled:to-gray-500 flex items-center gap-2 shadow-md hover:shadow-lg shadow-[#38bec9]/20"
                >
                    {loading ? (
                        <>
                            <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                            <span>Enviando</span>
                        </>
                    ) : (
                        <>
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                            </svg>
                            <span>Enviar</span>
                        </>
                    )}
                </button>
            </div>
        </div>
    )
}
