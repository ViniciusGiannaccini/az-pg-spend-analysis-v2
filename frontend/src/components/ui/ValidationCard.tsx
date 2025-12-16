import React from 'react'

export interface ValidationCheck {
    label: string
    status: 'ok' | 'warning' | 'error'
    message: string
}

export interface FileValidation {
    file: File
    content: string
    isValid: boolean
    checks: ValidationCheck[]
    previewData: any[]
}

interface ValidationCardProps {
    validation: FileValidation
    onClear: () => void
    disabled: boolean
}

export default function ValidationCard({
    validation,
    onClear,
    disabled
}: ValidationCardProps) {
    const allOk = validation.checks.every(c => c.status === 'ok')
    const hasError = validation.checks.some(c => c.status === 'error')

    return (
        <div className={`rounded-lg border overflow-hidden ${allOk ? 'border-green-200 bg-green-50/50' :
            hasError ? 'border-red-200 bg-red-50/50' :
                'border-yellow-200 bg-yellow-50/50'
            }`}>
            {/* Header with Semaphore */}
            <div className={`px-3 py-2 flex items-center justify-between border-b ${allOk ? 'bg-green-100/50 border-green-200' :
                hasError ? 'bg-red-100/50 border-red-200' :
                    'bg-yellow-100/50 border-yellow-200'
                }`}>
                <div className="flex items-center gap-2">
                    {/* Semaphore Light */}
                    <div className={`w-4 h-4 rounded-full shadow-inner ${allOk ? 'bg-green-500' : hasError ? 'bg-red-500' : 'bg-yellow-400'
                        }`}></div>
                    <span className="text-xs font-medium text-gray-700 truncate max-w-[120px]" title={validation.file.name}>
                        {validation.file.name}
                    </span>
                </div>
                <button
                    onClick={onClear}
                    className="text-xs text-gray-500 hover:text-red-600 transition-colors"
                    disabled={disabled}
                >
                    ✕
                </button>
            </div>

            {/* Checks */}
            <div className="p-2 space-y-1">
                {validation.checks.map((check, idx) => (
                    <div key={idx} className="flex items-center gap-2 text-xs">
                        {check.status === 'ok' ? (
                            <svg className="w-3.5 h-3.5 text-green-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                            </svg>
                        ) : check.status === 'warning' ? (
                            <svg className="w-3.5 h-3.5 text-yellow-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                            </svg>
                        ) : (
                            <svg className="w-3.5 h-3.5 text-red-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                            </svg>
                        )}
                        <span className="text-gray-600">
                            <span className="font-medium">{check.label}:</span> {check.message}
                        </span>
                    </div>
                ))}
            </div>
        </div>
    )
}
