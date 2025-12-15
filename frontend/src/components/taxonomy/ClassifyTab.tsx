import React, { useState, useCallback } from 'react'
import FileUpload from '@/components/FileUpload'
import * as XLSX from 'xlsx'

interface ValidationCheck {
    label: string
    status: 'ok' | 'warning' | 'error'
    message: string
}

interface FileValidation {
    file: File
    content: string
    isValid: boolean
    checks: ValidationCheck[]
    previewData: any[]
}

interface ClassifyTabProps {
    onFileSelect: (file: File, fileContent: string, hierarchyContent?: string) => void
    isProcessing: boolean
}

export default function ClassifyTab({ onFileSelect, isProcessing }: ClassifyTabProps) {
    const [baseValidation, setBaseValidation] = useState<FileValidation | null>(null)
    const [hierarchyValidation, setHierarchyValidation] = useState<FileValidation | null>(null)

    // Validate base file (needs SKU and Descrição columns)
    const validateBaseFile = useCallback((file: File, content: string) => {
        try {
            const bytes = Uint8Array.from(atob(content), c => c.charCodeAt(0))
            const workbook = XLSX.read(bytes, { type: 'array' })
            const sheet = workbook.Sheets[workbook.SheetNames[0]]
            const data: any[] = XLSX.utils.sheet_to_json(sheet)

            const checks: ValidationCheck[] = []
            const columns = data.length > 0 ? Object.keys(data[0]) : []
            const columnLower = columns.map(c => c.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, ''))

            // Check for description column
            const hasDesc = columnLower.some(c =>
                c.includes('descricao') || c.includes('description') || c.includes('item_description')
            )
            checks.push({
                label: 'Coluna Descrição',
                status: hasDesc ? 'ok' : 'error',
                message: hasDesc ? 'Encontrada' : 'Coluna de descrição não encontrada'
            })

            // Check row count
            const rowCount = data.length
            checks.push({
                label: 'Quantidade de Itens',
                status: rowCount > 0 ? 'ok' : 'error',
                message: `${rowCount} itens encontrados`
            })

            // Check for SKU column (warning only)
            const hasSku = columnLower.some(c =>
                c.includes('sku') || c.includes('codigo') || c.includes('code')
            )
            checks.push({
                label: 'Coluna SKU',
                status: hasSku ? 'ok' : 'warning',
                message: hasSku ? 'Encontrada' : 'Não encontrada (opcional)'
            })

            const isValid = hasDesc && rowCount > 0

            setBaseValidation({
                file,
                content,
                isValid,
                checks,
                previewData: data.slice(0, 3)
            })
        } catch (error) {
            setBaseValidation({
                file,
                content,
                isValid: false,
                checks: [{
                    label: 'Erro',
                    status: 'error',
                    message: 'Não foi possível ler o arquivo'
                }],
                previewData: []
            })
        }
    }, [])

    // Validate hierarchy file (needs N1, N2, N3, N4 columns)
    const validateHierarchyFile = useCallback((file: File, content: string) => {
        try {
            const bytes = Uint8Array.from(atob(content), c => c.charCodeAt(0))
            const workbook = XLSX.read(bytes, { type: 'array' })
            const sheet = workbook.Sheets[workbook.SheetNames[0]]
            const data: any[] = XLSX.utils.sheet_to_json(sheet)

            const checks: ValidationCheck[] = []
            const columns = data.length > 0 ? Object.keys(data[0]) : []
            const columnUpper = columns.map(c => c.toUpperCase().trim())

            // Check required columns
            const requiredCols = ['N1', 'N2', 'N3', 'N4']
            const missingCols = requiredCols.filter(col => !columnUpper.includes(col))

            checks.push({
                label: 'Colunas N1-N4',
                status: missingCols.length === 0 ? 'ok' : 'error',
                message: missingCols.length === 0
                    ? 'Todas presentes'
                    : `Faltando: ${missingCols.join(', ')}`
            })

            // Check unique N4 count
            const n4Col = columns.find(c => c.toUpperCase().trim() === 'N4')
            const uniqueN4s = n4Col ? new Set(data.map(r => r[n4Col]).filter(Boolean)).size : 0
            checks.push({
                label: 'Categorias N4',
                status: uniqueN4s > 0 ? 'ok' : 'warning',
                message: `${uniqueN4s} categorias únicas`
            })

            const isValid = missingCols.length === 0

            setHierarchyValidation({
                file,
                content,
                isValid,
                checks,
                previewData: data.slice(0, 3)
            })
        } catch (error) {
            setHierarchyValidation({
                file,
                content,
                isValid: false,
                checks: [{
                    label: 'Erro',
                    status: 'error',
                    message: 'Não foi possível ler o arquivo'
                }],
                previewData: []
            })
        }
    }, [])

    const handleBaseFileSelect = (file: File, content: string) => {
        validateBaseFile(file, content)
    }

    const handleHierarchySelect = (file: File, content: string) => {
        validateHierarchyFile(file, content)
    }

    const handleClearBase = () => {
        setBaseValidation(null)
    }

    const handleClearHierarchy = () => {
        setHierarchyValidation(null)
    }

    const handleSubmit = () => {
        if (baseValidation?.isValid) {
            onFileSelect(
                baseValidation.file,
                baseValidation.content,
                hierarchyValidation?.isValid ? hierarchyValidation.content : undefined
            )
        }
    }

    const canSubmit = baseValidation?.isValid && !isProcessing
    const hierarchyReady = hierarchyValidation === null || hierarchyValidation.isValid

    return (
        <div className="animate-fadeIn">
            {/* Two Column Grid Layout */}
            <div className="grid grid-cols-2 gap-6">
                {/* Left Column: Base File */}
                <div className="flex flex-col">
                    <h2 className="text-base font-semibold text-gray-800 mb-2 text-center">
                        📄 Arquivo Base (obrigatório)
                    </h2>
                    <div className="bg-[#38bec9]/10 border border-[#38bec9]/30 rounded-lg px-3 py-1.5 mb-3">
                        <p className="text-xs text-[#14919b] text-center">
                            <strong>Colunas:</strong> SKU | Descrição
                        </p>
                    </div>

                    {baseValidation ? (
                        <ValidationCard
                            validation={baseValidation}
                            onClear={handleClearBase}
                            disabled={isProcessing}
                        />
                    ) : (
                        <FileUpload onFileSelect={handleBaseFileSelect} disabled={isProcessing} />
                    )}
                </div>

                {/* Right Column: Hierarchy File */}
                <div className="flex flex-col border-l border-gray-200 pl-6">
                    <h2 className="text-base font-semibold text-gray-800 mb-2 text-center">
                        🌳 Hierarquia Customizada (opcional)
                    </h2>
                    <div className="bg-[#1c0957]/5 border border-[#1c0957]/20 rounded-lg px-3 py-1.5 mb-3">
                        <p className="text-xs text-[#1c0957] text-center">
                            <strong>Colunas:</strong> N1 | N2 | N3 | N4
                        </p>
                    </div>

                    {hierarchyValidation ? (
                        <ValidationCard
                            validation={hierarchyValidation}
                            onClear={handleClearHierarchy}
                            disabled={isProcessing}
                        />
                    ) : (
                        <FileUpload onFileSelect={handleHierarchySelect} disabled={isProcessing} />
                    )}
                </div>
            </div>

            {/* Submit Button */}
            {baseValidation && (
                <div className="mt-6 flex justify-center">
                    <button
                        onClick={handleSubmit}
                        disabled={!canSubmit || !hierarchyReady}
                        className={`px-8 py-3 text-sm font-semibold rounded-lg transition-all shadow-md ${canSubmit && hierarchyReady
                            ? 'bg-[#14919b] text-white hover:bg-[#0e7c86] hover:shadow-lg'
                            : 'bg-gray-200 text-gray-400 cursor-not-allowed'
                            }`}
                    >
                        {isProcessing ? 'Processando...' : 'Classificar Itens'}
                    </button>
                </div>
            )}


        </div>
    )
}

// Validation Card Component with Semaphore
function ValidationCard({
    validation,
    onClear,
    disabled
}: {
    validation: FileValidation
    onClear: () => void
    disabled: boolean
}) {
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
