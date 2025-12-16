import React, { useState, useCallback } from 'react'
import FileUpload from '@/components/FileUpload'
import * as XLSX from 'xlsx'
import { API_BASE_URL } from '@/lib/api'
import ValidationCard, { FileValidation, ValidationCheck } from '@/components/ui/ValidationCard'

interface DiscoveryTabProps {
    isProcessing: boolean
    onStartProcessing: () => void
    onFinishProcessing: () => void
    onSendToCopilot?: (message: string, preCalculatedResponse?: string) => void
    onSendSilent?: (message: string) => Promise<string | null>
}

export default function DiscoveryTab({ isProcessing, onStartProcessing, onFinishProcessing, onSendToCopilot, onSendSilent }: DiscoveryTabProps) {
    // Validation State
    const [validation, setValidation] = useState<FileValidation | null>(null)
    const [clusters, setClusters] = useState<Record<string, string[]> | null>(null)
    const [error, setError] = useState<string | null>(null)
    const [progressStatus, setProgressStatus] = useState<string | null>(null)
    const [taxonomyModel, setTaxonomyModel] = useState<'proprietary' | 'unspsc'>('proprietary')

    // Validation Logic (similar to ClassifyTab but simpler requirements)
    const validateFile = useCallback((file: File, content: string) => {
        // ... (omitted, no change)
        try {
            const bytes = Uint8Array.from(atob(content), c => c.charCodeAt(0))
            const workbook = XLSX.read(bytes, { type: 'array' })
            const sheet = workbook.Sheets[workbook.SheetNames[0]]
            const data: any[] = XLSX.utils.sheet_to_json(sheet)

            // ... (validation logic same as before)
            const checks: ValidationCheck[] = []
            const columns = data.length > 0 ? Object.keys(data[0]) : []
            const columnLower = columns.map(c => c.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, ''))

            // Check for description column (Required)
            const hasDesc = columnLower.some(c =>
                c.includes('descricao') || c.includes('description') ||
                c.includes('item_description') || c.includes('material_description') ||
                c.includes('texto breve') || c.includes('texto longo')
            )
            checks.push({
                label: 'Coluna Descrição',
                status: hasDesc ? 'ok' : 'error',
                message: hasDesc ? 'Encontrada' : 'Não encontrada '
            })

            // Check row count
            const rowCount = data.length
            checks.push({
                label: 'Quantidade de Itens',
                status: rowCount > 0 ? 'ok' : 'error',
                message: `${rowCount} itens encontrados`
            })

            const isValid = hasDesc && rowCount > 0

            setValidation({
                file,
                content,
                isValid,
                checks,
                previewData: data.slice(0, 3)
            })
            // Clear previous results
            setClusters(null)
            setError(null)
        } catch (error) {
            setValidation({
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

    const handleFileSelect = (selectedFile: File, content: string) => {
        validateFile(selectedFile, content)
    }

    const handleClear = () => {
        setValidation(null)
        setClusters(null)
    }

    const handleProcess = async () => {
        if (!validation?.isValid) return

        onStartProcessing()
        setError(null)
        setClusters(null)

        try {
            const response = await fetch(`${API_BASE_URL}/TaxonomyDiscovery`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ fileContent: validation.content })
            })

            if (!response.ok) {
                const text = await response.text()
                throw new Error(text || 'Falha ao processar descoberta.')
            }

            const data = await response.json()
            setClusters(data)
        } catch (err: any) {
            setError(err.message)
        } finally {
            onFinishProcessing()
        }
    }

    const handleCopyToClipboard = (clusterName: string, samples: string[]) => {
        const text = `**${clusterName}:** [${samples.join(', ')}]`
        navigator.clipboard.writeText(text)
    }

    const handleSendAllToCopilot = async () => {
        if (!clusters) return;

        const clusterCount = Object.keys(clusters).length
        const BATCH_SIZE = 50
        const isUnspsc = taxonomyModel === 'unspsc'

        const instruction = isUnspsc
            ? "Sugira a classificação UNSPSC completa (Segmento, Família, Classe, Mercadoria). Use APENAS os nomes descritivos das categorias, SEM códigos numéricos."
            : "Sugira Taxonomia (N4) e Hierarquia (N1-N3)"

        // If small enough or no silent sender available, use legacy method
        if (clusterCount <= BATCH_SIZE || !onSendSilent) {
            let message = `Aqui estão grupos de itens que encontrei. Por favor, ${instruction} para cada grupo:\n\n`;
            Object.entries(clusters).forEach(([name, samples]) => {
                message += `**${name}:** [${samples.join(', ')}]\n`
            })

            if (onSendToCopilot) {
                onSendToCopilot(message)
            } else {
                navigator.clipboard.writeText(message)
                alert("Conteúdo copiado para a área de transferência! Cole no chat.")
            }
            return
        }

        // AUTO-BATCHING MODE
        if (!confirm(`Existem ${clusterCount} grupos. O sistema enviará em lotes para garantir a melhor análise. Isso pode levar alguns minutos. Deseja iniciar?`)) {
            return
        }

        onStartProcessing()

        try {
            const allClusters = Object.entries(clusters)
            const totalBatches = Math.ceil(clusterCount / BATCH_SIZE)
            let accumulatedResponse = ""

            for (let i = 0; i < totalBatches; i++) {
                const start = i * BATCH_SIZE
                const end = start + BATCH_SIZE
                const batch = allClusters.slice(start, end)

                let batchMessage = `INSTRUCÃO: Analise este LOTE ${i + 1}/${totalBatches} de grupos. ${instruction}.\n\n`;
                batch.forEach(([name, samples]) => {
                    batchMessage += `**${name}:** [${samples.join(', ')}]\n`
                })

                // Send silently
                // We update logic to use onSendSilent which returns Promise<string | null>
                const response = await onSendSilent(batchMessage)

                if (response) {
                    accumulatedResponse += `\n\n## Lote ${i + 1}/${totalBatches}\n${response}`
                } else {
                    throw new Error(`Falha ao processar lote ${i + 1}`)
                }
            }

            // All batches done. Send accumulated result to Chat via Injection
            if (onSendToCopilot) {
                onSendToCopilot(
                    `Analise todos os ${clusterCount} grupos descobertos e mostre o resultado consolidado da classificação ${isUnspsc ? 'UNSPSC' : 'Proprietária'}.`,
                    accumulatedResponse
                )
            }

        } catch (err) {
            alert("Ocorreu um erro durante o processamento em lote. Tente novamente ou use um arquivo menor.")
            console.error(err)
        } finally {
            onFinishProcessing()
        }
    }

    return (
        <div className="animate-fadeIn space-y-6">
            <div className="text-center mb-6">
                <h2 className="text-lg font-bold text-[#102a43]">Descoberta de Taxonomia (IA)</h2>
                <p className="text-sm text-gray-600">
                    Envie seus dados brutos e deixe a IA agrupar itens similares para você nomear.
                </p>
            </div>

            {/* Upload Section */}
            {!clusters && (
                <div className="max-w-xl mx-auto">
                    <div className="bg-[#38bec9]/10 border border-[#38bec9]/30 rounded-lg px-3 py-1.5 mb-3">
                        <p className="text-xs text-[#14919b] text-center">
                            <strong>Colunas:</strong> Descrição (obrigatório) | SKU (opcional)
                        </p>
                    </div>

                    {validation ? (
                        <ValidationCard
                            validation={validation}
                            onClear={handleClear}
                            disabled={isProcessing}
                        />
                    ) : (
                        <FileUpload onFileSelect={handleFileSelect} disabled={isProcessing} />
                    )}

                    {validation?.isValid && (
                        <div className="mt-4 flex justify-center">
                            <button
                                onClick={handleProcess}
                                disabled={isProcessing}
                                className="px-6 py-2 bg-[#38bec9] text-white rounded-lg hover:bg-[#2c9ca6] transition-colors shadow-md disabled:opacity-50"
                            >
                                {isProcessing ? 'Analisando Padrões...' : 'Descobrir Padrões'}
                            </button>
                        </div>
                    )}
                    {error && (
                        <div className="mt-4 p-3 bg-red-50 text-red-600 text-sm rounded-lg border border-red-100 text-center">
                            {error}
                        </div>
                    )}
                </div>
            )}

            {/* Results Section */}
            {clusters && (
                <div className="space-y-4">
                    <div className="flex items-center justify-between bg-green-50 p-4 rounded-xl border border-green-100">
                        <div>
                            <h3 className="font-bold text-green-800">Análise Concluída!</h3>
                            <p className="text-sm text-green-700">Encontramos {Object.keys(clusters).length} grupos distintos.</p>
                        </div>
                        <div className="flex gap-2">
                            <button
                                onClick={() => setClusters(null)}
                                className="px-4 py-2 text-sm text-gray-500 hover:text-gray-700 underline"
                            >
                                Reiniciar
                            </button>
                            <button
                                onClick={() => {
                                    // Generate Excel Draft
                                    if (!clusters) return
                                    const rows: any[] = []
                                    Object.entries(clusters).forEach(([clusterName, samples]) => {
                                        // Create a row for each cluster with placeholders
                                        rows.push({
                                            'N1': '',
                                            'N2': '',
                                            'N3': '',
                                            'N4': '', // User to fill
                                            'Cluster_ID': clusterName,
                                            'Exemplos': samples.join('; ')
                                        })
                                    })

                                    const ws = XLSX.utils.json_to_sheet(rows)
                                    const wb = XLSX.utils.book_new()
                                    XLSX.utils.book_append_sheet(wb, ws, "Rascunho Taxonomia")
                                    XLSX.writeFile(wb, "Rascunho_Taxonomia_Discovery.xlsx")
                                }}
                                className="px-4 py-2 bg-indigo-50 text-indigo-700 border border-indigo-200 text-sm font-medium rounded-lg hover:bg-indigo-100 transition-all flex items-center gap-2"
                            >
                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                                </svg>
                                Baixar Rascunho Excel
                            </button>
                            <button
                                onClick={handleSendAllToCopilot}
                                className="px-4 py-2 bg-[#2a1177] text-white text-sm font-medium rounded-lg hover:bg-[#1c0957] transition-all shadow-md flex items-center gap-2"
                            >
                                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                                </svg>
                                Enviar para Copilot
                            </button>
                        </div>
                    </div>

                    {/* Taxonomy Model Toggle */}
                    <div className="bg-gray-50 rounded-lg p-3 border border-gray-200 flex items-center justify-between">
                        <span className="text-sm font-medium text-gray-700">Modelo de Taxonomia:</span>
                        <div className="flex bg-white rounded-lg border border-gray-200 p-1">
                            <button
                                onClick={() => setTaxonomyModel('proprietary')}
                                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all ${taxonomyModel === 'proprietary'
                                    ? 'bg-[#2a1177] text-white shadow-sm'
                                    : 'text-gray-500 hover:text-gray-700'
                                    }`}
                            >
                                Padrão (N1-N4)
                            </button>
                            <button
                                onClick={() => setTaxonomyModel('unspsc')}
                                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all ${taxonomyModel === 'unspsc'
                                    ? 'bg-[#2a1177] text-white shadow-sm'
                                    : 'text-gray-500 hover:text-gray-700'
                                    }`}
                            >
                                UNSPSC
                            </button>
                        </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {Object.entries(clusters).map(([clusterName, samples]) => (
                            <div key={clusterName} className="bg-white p-4 rounded-xl border border-gray-200 hover:shadow-md transition-shadow">
                                <div className="flex justify-between items-start mb-2">
                                    <h4 className="font-bold text-[#102a43]">{clusterName}</h4>
                                    <button
                                        onClick={() => handleCopyToClipboard(clusterName, samples)}
                                        className="text-xs text-[#38bec9] hover:text-[#2c9ca6]"
                                        title="Copiar amostras"
                                    >
                                        Copiar
                                    </button>
                                </div>
                                <div className="flex flex-wrap gap-1.5">
                                    {samples.map((sample, idx) => (
                                        <span key={idx} className="px-2 py-1 bg-gray-100 text-gray-600 text-xs rounded-md">
                                            {sample}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    )
}
