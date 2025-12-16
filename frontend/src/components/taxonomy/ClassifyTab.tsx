import React, { useState, useCallback } from 'react'
import FileUpload from '@/components/FileUpload'
import * as XLSX from 'xlsx'
import ValidationCard, { FileValidation, ValidationCheck } from '@/components/ui/ValidationCard'

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


