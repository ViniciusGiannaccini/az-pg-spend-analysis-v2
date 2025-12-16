import React, { useState, useCallback } from 'react'
import FileUpload from '@/components/FileUpload'
import * as XLSX from 'xlsx'
import { API_BASE_URL } from '@/lib/api'
import { base64ToBlob } from '@/hooks/useTaxonomySession'
import ValidationCard, { FileValidation, ValidationCheck } from '@/components/ui/ValidationCard'

interface ZeroShotTabProps {
    isProcessing: boolean
    onStartProcessing: () => void
    onFinishProcessing: () => void
}

export default function ZeroShotTab({ isProcessing, onStartProcessing, onFinishProcessing }: ZeroShotTabProps) {
    const [dataValidation, setDataValidation] = useState<FileValidation | null>(null)
    const [taxonomyValidation, setTaxonomyValidation] = useState<FileValidation | null>(null)

    const [error, setError] = useState<string | null>(null)
    const [result, setResult] = useState<{ filename: string, url: string } | null>(null)

    // Validate Data File (Needs SKU/Description)
    const validateDataFile = useCallback((file: File, content: string) => {
        try {
            const bytes = Uint8Array.from(atob(content), c => c.charCodeAt(0))
            const workbook = XLSX.read(bytes, { type: 'array' })
            const sheet = workbook.Sheets[workbook.SheetNames[0]]
            const data: any[] = XLSX.utils.sheet_to_json(sheet)

            const checks: ValidationCheck[] = []
            const columns = data.length > 0 ? Object.keys(data[0]) : []
            const columnLower = columns.map(c => c.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, ''))

            const hasDesc = columnLower.some(c =>
                c.includes('descricao') || c.includes('description') ||
                c.includes('item_description') || c.includes('material_description') ||
                c.includes('texto breve') || c.includes('texto longo')
            )
            checks.push({
                label: 'Coluna Descrição',
                status: hasDesc ? 'ok' : 'error',
                message: hasDesc ? 'Encontrada' : 'Não encontrada (obrigatório)'
            })

            checks.push({
                label: 'Qtd Itens',
                status: data.length > 0 ? 'ok' : 'error',
                message: `${data.length} linhas`
            })

            setDataValidation({
                file,
                content,
                isValid: hasDesc && data.length > 0,
                checks,
                previewData: data.slice(0, 3)
            })
            setResult(null)
            setError(null)
        } catch (error) {
            setDataValidation({
                file,
                content,
                isValid: false,
                checks: [{ label: 'Erro', status: 'error', message: 'Falha na leitura' }],
                previewData: []
            })
        }
    }, [])

    // Validate Taxonomy File (Needs N4 or N1-N4)
    const validateTaxonomyFile = useCallback((file: File, content: string) => {
        try {
            const bytes = Uint8Array.from(atob(content), c => c.charCodeAt(0))
            const workbook = XLSX.read(bytes, { type: 'array' })
            const sheet = workbook.Sheets[workbook.SheetNames[0]]
            const data: any[] = XLSX.utils.sheet_to_json(sheet)

            const checks: ValidationCheck[] = []
            const columns = data.length > 0 ? Object.keys(data[0]) : []
            const columnUpper = columns.map(c => c.toUpperCase().trim())

            const hasN4 = columnUpper.includes('N4') || columnUpper.includes('CATEGORIA')
            checks.push({
                label: 'Coluna N4',
                status: hasN4 ? 'ok' : 'error',
                message: hasN4 ? 'Encontrada' : 'Não encontrada (N4 ou Categoria)'
            })

            const hasN1 = columnUpper.includes('N1')
            checks.push({
                label: 'Hierarquia Completa',
                status: hasN1 ? 'ok' : 'warning',
                message: hasN1 ? 'N1-N4 Presentes' : 'Apenas N4 detectado'
            })

            setTaxonomyValidation({
                file,
                content,
                isValid: hasN4,
                checks,
                previewData: data.slice(0, 3)
            })
            setResult(null)
            setError(null)
        } catch (error) {
            setTaxonomyValidation({
                file,
                content,
                isValid: false,
                checks: [{ label: 'Erro', status: 'error', message: 'Falha na leitura' }],
                previewData: []
            })
        }
    }, [])

    const handleDataFileSelect = (selectedFile: File, content: string) => {
        validateDataFile(selectedFile, content)
    }

    const handleTaxonomyInput = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0] || null
        if (file) {
            const reader = new FileReader()
            reader.onload = (ev) => {
                const content = (ev.target?.result as string).split(',')[1]
                validateTaxonomyFile(file, content)
            }
            reader.readAsDataURL(file)
        }
    }

    const handleClearData = () => setDataValidation(null)
    const handleClearTaxonomy = () => setTaxonomyValidation(null)

    const handleProcess = async () => {
        if (!dataValidation?.isValid) {
            setError("Por favor, envie o arquivo de dados válido.")
            return
        }
        if (!taxonomyValidation?.isValid) {
            setError("Por favor, envie o arquivo de taxonomia válido.")
            return
        }

        onStartProcessing()
        setError(null)
        setResult(null)

        try {
            const response = await fetch(`${API_BASE_URL}/ZeroShotClassify`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    fileContent: dataValidation.content,
                    taxonomyFile: taxonomyValidation.content,
                    threshold: 0.45
                })
            })

            if (!response.ok) {
                const text = await response.text()
                throw new Error(text || 'Falha na classificação Zero-Shot.')
            }

            const data = await response.json()

            // Handle Download
            const blob = base64ToBlob(data.fileContent,
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            const url = window.URL.createObjectURL(blob)

            setResult({
                filename: data.filename || 'classificacao_zeroshot.xlsx',
                url: url
            })

        } catch (err: any) {
            setError(err.message)
        } finally {
            onFinishProcessing()
        }
    }

    return (
        <div className="animate-fadeIn space-y-6">
            <div className="text-center mb-6">
                <h2 className="text-lg font-bold text-[#102a43]">Classificação Zero-Shot (IA)</h2>
                <p className="text-sm text-gray-600">
                    Classifique itens sem treinar modelos, apenas fornecendo os nomes das categorias.
                </p>
            </div>

            {!result ? (
                <div className="grid grid-cols-2 gap-6 max-w-4xl mx-auto">
                    {/* Left: Data File */}
                    <div className="space-y-4">
                        <h3 className="font-semibold text-gray-700">1. Arquivo de Dados</h3>
                        <div className="bg-[#38bec9]/10 border border-[#38bec9]/30 rounded-lg px-3 py-1.5 mb-3">
                            <p className="text-xs text-[#14919b] text-center">
                                <strong>Colunas:</strong> SKU | Descrição
                            </p>
                        </div>

                        {dataValidation ? (
                            <ValidationCard
                                validation={dataValidation}
                                onClear={handleClearData}
                                disabled={isProcessing}
                            />
                        ) : (
                            <FileUpload onFileSelect={handleDataFileSelect} disabled={isProcessing} />
                        )}
                    </div>

                    {/* Right: Taxonomy File */}
                    <div className="space-y-4">
                        <h3 className="font-semibold text-gray-700">2. Arquivo de Taxonomia (N1-N4)</h3>
                        <div className="bg-[#1c0957]/5 border border-[#1c0957]/20 rounded-lg px-3 py-1.5 mb-3">
                            <p className="text-xs text-[#1c0957] text-center">
                                <strong>Colunas:</strong> N1 | N2 | N3 | N4
                            </p>
                        </div>

                        {taxonomyValidation ? (
                            <ValidationCard
                                validation={taxonomyValidation}
                                onClear={handleClearTaxonomy}
                                disabled={isProcessing}
                            />
                        ) : (
                            <div className="border-2 border-dashed rounded-xl p-8 text-center transition-all duration-300 relative overflow-hidden group border-gray-300 bg-gradient-to-br from-gray-50 to-white hover:border-[#38bec9]/50 hover:shadow-md hover:shadow-gray-200/50 cursor-pointer">
                                <div className="absolute inset-0 opacity-[0.03] pointer-events-none">
                                    <div className="absolute inset-0" style={{
                                        backgroundImage: 'radial-gradient(circle at 2px 2px, #1c0957 1px, transparent 0)',
                                        backgroundSize: '24px 24px'
                                    }} />
                                </div>

                                <input
                                    type="file"
                                    accept=".xlsx, .xls, .csv"
                                    onChange={handleTaxonomyInput}
                                    className="hidden"
                                    id="taxonomy-upload"
                                    disabled={isProcessing}
                                />
                                <label
                                    htmlFor="taxonomy-upload"
                                    className="cursor-pointer flex flex-col items-center gap-4 relative z-10 w-full h-full"
                                >
                                    <div className="w-16 h-16 rounded-2xl flex items-center justify-center transition-all duration-300 bg-gray-100 text-gray-400 group-hover:bg-[#1c0957]/10 group-hover:text-[#1c0957]">
                                        <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                                            <path strokeLinecap="round" strokeLinejoin="round" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                                        </svg>
                                    </div>
                                    <div>
                                        <span className="text-sm font-semibold text-gray-700 group-hover:text-gray-900 transition-colors block">
                                            {taxonomyValidation?.file ? taxonomyValidation.file.name : "Carregar Taxonomia"}
                                        </span>
                                        <span className="text-xs text-gray-400 mt-1.5 block">
                                            Excel com colunas N1, N2, N3, N4
                                        </span>
                                    </div>
                                </label>
                            </div>
                        )}
                    </div>

                    {/* Submit */}
                    <div className="col-span-2 flex flex-col items-center mt-4">
                        {error && (
                            <div className="mb-4 p-3 bg-red-50 text-red-600 text-sm rounded-lg border border-red-100">
                                {error}
                            </div>
                        )}

                        <button
                            onClick={handleProcess}
                            disabled={isProcessing || !dataValidation?.isValid || !taxonomyValidation?.isValid}
                            className={`px-8 py-3 font-semibold rounded-lg transition-all shadow-md ${isProcessing || !dataValidation?.isValid || !taxonomyValidation?.isValid
                                ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                                : 'bg-[#1c0957] text-white hover:bg-[#2a1177] hover:shadow-lg'
                                }`}
                        >
                            {isProcessing ? 'Classificando via Semântica...' : 'Executar Classificação'}
                        </button>
                    </div>
                </div>
            ) : (
                /* Success View */
                <div className="max-w-md mx-auto text-center space-y-6 pt-10">
                    <div className="w-16 h-16 bg-green-100 text-green-600 rounded-full flex items-center justify-center mx-auto mb-4">
                        <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                    </div>
                    <h3 className="text-xl font-bold text-gray-800">Classificação Concluída!</h3>
                    <p className="text-gray-600">Seu arquivo foi processado utilizando inteligência semântica.</p>

                    <a
                        href={result.url}
                        download={result.filename}
                        className="inline-block w-full py-4 bg-[#38bec9] text-white font-bold rounded-xl shadow-lg hover:bg-[#2c9ca6] transition-transform hover:-translate-y-0.5"
                    >
                        Baixar Resultado
                    </a>

                    <button
                        onClick={() => setResult(null)}
                        className="text-gray-400 hover:text-gray-600 text-sm underline mt-4"
                    >
                        Classificar outro arquivo
                    </button>
                </div>
            )}
        </div>
    )
}
