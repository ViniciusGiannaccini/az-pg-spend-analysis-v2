import React, { useState, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { apiClient } from '@/lib/api'

interface ModelInfo {
    sector: string
    version_id: string
    hierarchy: {
        N1_count: number
        N2_count: number
        N3_count: number
        N4_count: number
        tree: Record<string, Record<string, Record<string, string[]>>>
    }
    training_stats: {
        total_descriptions: number
        by_n4: { N4: string; count: number }[]
    }
    metrics: {
        accuracy?: number
        f1_macro?: number
        total_samples?: number
    }
    comparison?: {
        previous_version: string
        metrics: {
            accuracy: number
            f1_macro?: number
            total_samples: number
            n1_count: number
            n2_count: number
            n3_count: number
            n4_count: number
        }
    }
}

interface TrainingDataRow {
    row_id: number
    Descrição: string
    N1: string
    N2: string
    N3: string
    N4: string
    added_version: string
    added_at: string
    Ocorrências?: number
}

interface ModelHistoryEntry {
    version_id: string
    timestamp: string
    status?: string
    metrics: {
        accuracy: number
        f1_macro?: number
    }
}

interface ModelViewerOverlayProps {
    sector: string
    modelHistory: ModelHistoryEntry[]
    onClose: () => void
    onRestoreModel?: (versionId: string) => void
    onRefresh?: () => void
}

function DiffIndicator({ current, previous, isPercent = false, invert = false, label }: { current: number; previous: number; isPercent?: boolean; invert?: boolean; label?: string }) {
    if (previous === undefined || previous === null) return null
    const diff = current - previous
    if (diff === 0) return null

    const isPositive = diff > 0
    const isGood = invert ? !isPositive : isPositive
    const color = isGood ? 'text-green-600' : 'text-red-600'
    const Arrow = isPositive ? '▲' : '▼'

    // Calculate percentage change relative to previous
    let pctStr = ''
    if (previous !== 0) {
        const pct = (diff / previous) * 100
        pctStr = ` (${isPositive ? '+' : ''}${pct.toFixed(1)}%)`
    }

    return (
        <span className={`ml-1 text-xs font-bold ${color} flex items-center inline-flex`} title={`Anterior: ${previous}`}>
            <span className="mr-0.5">{Arrow}</span>
            {isPercent
                ? `${Math.abs(diff * 100).toFixed(1)}%`
                : `${Math.abs(diff)}${pctStr}`
            }
        </span>
    )
}

export default function ModelViewerOverlay({ sector, modelHistory, onClose, onRestoreModel, onRefresh }: ModelViewerOverlayProps) {
    const [activeTab, setActiveTab] = useState<'tree' | 'stats' | 'data'>('tree')
    const [treeViewMode, setTreeViewMode] = useState<'hierarchical' | 'table'>('hierarchical')
    const [modelInfo, setModelInfo] = useState<ModelInfo | null>(null)
    const [isLoading, setIsLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [expandedN1, setExpandedN1] = useState<Record<string, boolean>>({})
    const [expandedN2, setExpandedN2] = useState<Record<string, boolean>>({})
    const [expandedN3, setExpandedN3] = useState<Record<string, boolean>>({})
    const [mounted, setMounted] = useState(false)

    useEffect(() => {
        setMounted(true)
        return () => setMounted(false)
    }, [])

    // Version selection state
    const activeVersion = modelHistory.find(h => h.status === 'active')?.version_id || modelHistory[0]?.version_id
    const [selectedVersion, setSelectedVersion] = useState<string>(activeVersion || '')
    const isSelectedActive = selectedVersion === activeVersion

    // Data tab state
    const [trainingData, setTrainingData] = useState<TrainingDataRow[]>([])
    const [dataPage, setDataPage] = useState(1)
    const [dataTotal, setDataTotal] = useState(0)
    const [dataTotalPages, setDataTotalPages] = useState(0)
    const [dataVersions, setDataVersions] = useState<string[]>([])
    const [dataVersionFilter, setDataVersionFilter] = useState<string>('')
    const [dataSearch, setDataSearch] = useState('')
    const [selectedRows, setSelectedRows] = useState<number[]>([])
    const [isLoadingData, setIsLoadingData] = useState(false)
    const [isDeleting, setIsDeleting] = useState(false)

    useEffect(() => {
        if (selectedVersion) {
            loadModelInfo()
        }
    }, [sector, selectedVersion])

    useEffect(() => {
        if (activeTab === 'data') {
            loadTrainingData()
        }
    }, [activeTab, dataPage, dataVersionFilter, sector])

    // Sync selectedVersion if it disappears from history (e.g. deleted)
    useEffect(() => {
        if (modelHistory.length > 0) {
            const exists = modelHistory.find(h => h.version_id === selectedVersion)
            if (!exists) {
                const newActive = modelHistory.find(h => h.status === 'active') || modelHistory[0]
                setSelectedVersion(newActive.version_id)
            }
        }
    }, [modelHistory, selectedVersion])

    const loadTrainingData = async () => {
        setIsLoadingData(true)
        try {
            const response = await apiClient.getTrainingData(sector, dataPage, 50, {
                version: dataVersionFilter || undefined,
                search: dataSearch || undefined
            })
            setTrainingData(response.data)
            setDataTotal(response.total)
            setDataTotalPages(response.total_pages)
            setDataVersions(response.versions || [])
        } catch (err) {
            console.error('Error loading training data:', err)
        } finally {
            setIsLoadingData(false)
        }
    }

    const handleDeleteSelected = async () => {
        if (selectedRows.length === 0) return

        // Build items list from selected rows (to delete all duplicates)
        const selectedItems = trainingData
            .filter(row => selectedRows.includes(row.row_id))
            .map(row => ({
                descricao: row.Descrição,
                n4: row.N4,
                version: row.added_version
            }))

        const totalOccurrences = trainingData
            .filter(row => selectedRows.includes(row.row_id))
            .reduce((sum, row) => sum + (row.Ocorrências || 1), 0)

        if (!confirm(`Excluir ${selectedRows.length} itens (${totalOccurrences} registros totais incluindo duplicatas)?`)) return

        setIsDeleting(true)
        try {
            await apiClient.deleteTrainingData(sector, { items: selectedItems })
            setSelectedRows([])
            loadTrainingData()
        } catch (err) {
            alert('Erro ao excluir registros')
        } finally {
            setIsDeleting(false)
        }
    }

    const handleDeleteVersion = async (version: string) => {
        if (!confirm(`Excluir TODOS os registros da versão ${version}?`)) return

        setIsDeleting(true)
        try {
            await apiClient.deleteTrainingData(sector, { version })
            setDataVersionFilter('')  // Reset filter
            loadTrainingData()
            if (onRefresh) onRefresh()  // Refresh parent data
        } catch (err) {
            alert('Erro ao excluir versão')
        } finally {
            setIsDeleting(false)
        }
    }

    const handleSearch = () => {
        setDataPage(1)
        loadTrainingData()
    }

    const handleRestoreAndDelete = async () => {
        if (!selectedVersion || !onRestoreModel) return

        // Identifica qual versão deletar (a versão atual que está sendo visualizada é a que queremos manter)
        // Na verdade, precisamos excluir as versões DEPOIS desta que estamos restaurando
        // Por ora, vamos apenas restaurar e avisar que os dados permanecem
        if (!confirm(`Restaurar modelo para ${selectedVersion}? Os dados de treinamento serão mantidos para referência.`)) return

        onRestoreModel(selectedVersion)
    }

    const toggleRowSelection = (rowId: number) => {
        setSelectedRows(prev =>
            prev.includes(rowId)
                ? prev.filter(id => id !== rowId)
                : [...prev, rowId]
        )
    }

    const toggleSelectAll = () => {
        if (selectedRows.length === trainingData.length) {
            setSelectedRows([])
        } else {
            setSelectedRows(trainingData.map(row => row.row_id))
        }
    }

    const loadModelInfo = async () => {
        if (!selectedVersion) return
        setIsLoading(true)
        setError(null)
        try {
            const data = await apiClient.getModelInfo(sector, selectedVersion)
            setModelInfo(data)
        } catch (err: any) {
            setError(err.message || 'Erro ao carregar informações do modelo')
        } finally {
            setIsLoading(false)
        }
    }

    const toggleN1 = (n1: string) => {
        setExpandedN1(prev => ({ ...prev, [n1]: !prev[n1] }))
    }
    const toggleN2 = (key: string) => {
        setExpandedN2(prev => ({ ...prev, [key]: !prev[key] }))
    }
    const toggleN3 = (key: string) => {
        setExpandedN3(prev => ({ ...prev, [key]: !prev[key] }))
    }

    // Flatten tree for table view
    const getTableData = () => {
        if (!modelInfo) return []
        const rows: { N1: string; N2: string; N3: string; N4: string }[] = []
        Object.entries(modelInfo.hierarchy.tree).forEach(([n1, n2s]) => {
            Object.entries(n2s).forEach(([n2, n3s]) => {
                Object.entries(n3s).forEach(([n3, n4s]) => {
                    n4s.forEach(n4 => {
                        rows.push({ N1: n1, N2: n2, N3: n3, N4: n4 })
                    })
                })
            })
        })
        return rows
    }

    const tabs = [
        { id: 'tree', label: '🌳 Árvore' },
        { id: 'stats', label: '📊 Estatísticas' },
        { id: 'data', label: '📄 Dados' }
    ]

    const content = (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-6">
            <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />

            <div className="relative w-full max-w-5xl h-[85vh] bg-white rounded-2xl shadow-2xl flex flex-col overflow-hidden animate-slideUp">
                {/* Header - Dark Blue */}
                <div className="bg-[#1c0957] px-6 py-4 flex items-center justify-between border-b border-white/10 shrink-0">
                    <div>
                        <h2 className="text-xl font-bold text-white">Visualizador de Modelos - {sector}</h2>
                        <p className="text-sm text-white/60">Compare versões e métricas de treinamento</p>
                    </div>
                    <div className="flex items-center gap-4">
                        <select
                            value={selectedVersion}
                            onChange={(e) => setSelectedVersion(e.target.value)}
                            className="px-3 py-1.5 text-sm bg-white/20 text-white border border-white/30 rounded-lg focus:ring-2 focus:ring-white/50 focus:outline-none cursor-pointer"
                        >
                            {modelHistory.map(h => (
                                <option key={h.version_id} value={h.version_id} className="text-gray-900">
                                    {h.version_id} {h.status === 'active' ? '(Ativo)' : ''} - {h.metrics?.accuracy ? `${(h.metrics.accuracy * 100).toFixed(1)}%` : 'N/A'}
                                </option>
                            ))}
                        </select>
                        {isSelectedActive && (
                            <span className="px-2 py-0.5 text-xs bg-green-500 text-white rounded-full">Ativo</span>
                        )}
                    </div>
                    <p className="text-sm text-white/70 hidden md:block">Visualização detalhada do modelo</p>
                    <button
                        onClick={onClose}
                        className="p-2 text-white/60 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
                    >
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>

                {/* Tabs */}
                <div className="flex border-b border-gray-200 bg-gray-50">
                    {tabs.map(tab => (
                        <button
                            key={tab.id}
                            onClick={() => setActiveTab(tab.id as any)}
                            className={`px-6 py-3 text-sm font-medium transition-colors ${activeTab === tab.id
                                ? 'text-[#14919b] border-b-2 border-[#14919b] bg-white'
                                : 'text-gray-600 hover:text-gray-800 hover:bg-gray-100'
                                }`}
                        >
                            {tab.label}
                        </button>
                    ))}
                </div>

                {/* Content */}
                <div className="flex-1 overflow-auto p-6">
                    {isLoading ? (
                        <div className="flex items-center justify-center h-64">
                            <div className="animate-spin rounded-full h-10 w-10 border-4 border-gray-200 border-t-[#14919b]"></div>
                        </div>
                    ) : error ? (
                        <div className="text-center text-red-600 py-10">
                            <p>{error}</p>
                            <button onClick={loadModelInfo} className="mt-4 text-[#14919b] hover:underline">
                                Tentar novamente
                            </button>
                        </div>
                    ) : modelInfo && (
                        <>
                            {/* Tree Tab */}
                            {activeTab === 'tree' && (
                                <div className="space-y-4">
                                    {/* Header with counters and toggle */}
                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-4 text-sm text-gray-600">
                                            <span className="px-2 py-1 bg-blue-100 rounded flex items-center">
                                                N1: {modelInfo.hierarchy.N1_count}
                                                {modelInfo.comparison?.metrics && (
                                                    <DiffIndicator
                                                        current={modelInfo.hierarchy.N1_count}
                                                        previous={modelInfo.comparison.metrics.n1_count}
                                                    />
                                                )}
                                            </span>
                                            <span className="px-2 py-1 bg-green-100 rounded flex items-center">
                                                N2: {modelInfo.hierarchy.N2_count}
                                                {modelInfo.comparison?.metrics && (
                                                    <DiffIndicator
                                                        current={modelInfo.hierarchy.N2_count}
                                                        previous={modelInfo.comparison.metrics.n2_count}
                                                    />
                                                )}
                                            </span>
                                            <span className="px-2 py-1 bg-yellow-100 rounded flex items-center">
                                                N3: {modelInfo.hierarchy.N3_count}
                                                {modelInfo.comparison?.metrics && (
                                                    <DiffIndicator
                                                        current={modelInfo.hierarchy.N3_count}
                                                        previous={modelInfo.comparison.metrics.n3_count}
                                                    />
                                                )}
                                            </span>
                                            <span className="px-2 py-1 bg-purple-100 rounded flex items-center">
                                                N4: {modelInfo.hierarchy.N4_count}
                                                {modelInfo.comparison?.metrics && (
                                                    <DiffIndicator
                                                        current={modelInfo.hierarchy.N4_count}
                                                        previous={modelInfo.comparison.metrics.n4_count}
                                                    />
                                                )}
                                            </span>
                                        </div>

                                        {/* Toggle */}
                                        <div className="flex items-center bg-gray-100 rounded-lg p-1">
                                            <button
                                                onClick={() => setTreeViewMode('hierarchical')}
                                                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all ${treeViewMode === 'hierarchical'
                                                    ? 'bg-white text-gray-800 shadow-sm'
                                                    : 'text-gray-500 hover:text-gray-700'
                                                    }`}
                                            >
                                                Hierárquica
                                            </button>
                                            <button
                                                onClick={() => setTreeViewMode('table')}
                                                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all ${treeViewMode === 'table'
                                                    ? 'bg-white text-gray-800 shadow-sm'
                                                    : 'text-gray-500 hover:text-gray-700'
                                                    }`}
                                            >
                                                Tabela
                                            </button>
                                        </div>
                                    </div>

                                    {/* Table View */}
                                    {treeViewMode === 'table' && (
                                        <div className="border border-gray-200 rounded-lg overflow-hidden">
                                            <table className="min-w-full divide-y divide-gray-200">
                                                <thead className="bg-gray-50">
                                                    <tr>
                                                        <th className="px-4 py-3 text-left text-xs font-semibold text-blue-600 uppercase tracking-wider">N1</th>
                                                        <th className="px-4 py-3 text-left text-xs font-semibold text-green-600 uppercase tracking-wider">N2</th>
                                                        <th className="px-4 py-3 text-left text-xs font-semibold text-yellow-600 uppercase tracking-wider">N3</th>
                                                        <th className="px-4 py-3 text-left text-xs font-semibold text-purple-600 uppercase tracking-wider">N4</th>
                                                    </tr>
                                                </thead>
                                                <tbody className="bg-white divide-y divide-gray-100">
                                                    {getTableData().map((row, idx) => (
                                                        <tr key={idx} className="hover:bg-gray-50">
                                                            <td className="px-4 py-2 text-sm text-gray-700">{row.N1}</td>
                                                            <td className="px-4 py-2 text-sm text-gray-700">{row.N2}</td>
                                                            <td className="px-4 py-2 text-sm text-gray-700">{row.N3}</td>
                                                            <td className="px-4 py-2 text-sm text-gray-700">{row.N4}</td>
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        </div>
                                    )}

                                    {/* Hierarchical View */}
                                    {treeViewMode === 'hierarchical' && (
                                        <>
                                            {Object.entries(modelInfo.hierarchy.tree).map(([n1, n2s]) => (
                                                <div key={n1} className="border border-gray-200 rounded-lg overflow-hidden">
                                                    <button
                                                        onClick={() => toggleN1(n1)}
                                                        className="w-full flex items-center justify-between px-4 py-3 bg-blue-50 hover:bg-blue-100 transition-colors"
                                                    >
                                                        <span className="font-semibold text-blue-800">{n1}</span>
                                                        <svg className={`w-5 h-5 text-blue-600 transition-transform ${expandedN1[n1] ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                                        </svg>
                                                    </button>

                                                    {expandedN1[n1] && (
                                                        <div className="pl-4 py-2 space-y-1">
                                                            {Object.entries(n2s).map(([n2, n3s]) => (
                                                                <div key={`${n1}-${n2}`} className="border-l-2 border-green-300">
                                                                    <button
                                                                        onClick={() => toggleN2(`${n1}-${n2}`)}
                                                                        className="w-full flex items-center justify-between px-4 py-2 hover:bg-green-50 transition-colors"
                                                                    >
                                                                        <span className="font-medium text-green-700">{n2}</span>
                                                                        <svg className={`w-4 h-4 text-green-600 transition-transform ${expandedN2[`${n1}-${n2}`] ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                                                        </svg>
                                                                    </button>

                                                                    {expandedN2[`${n1}-${n2}`] && (
                                                                        <div className="pl-4 py-1 space-y-1">
                                                                            {Object.entries(n3s).map(([n3, n4s]) => (
                                                                                <div key={`${n1}-${n2}-${n3}`} className="border-l-2 border-yellow-300">
                                                                                    <button
                                                                                        onClick={() => toggleN3(`${n1}-${n2}-${n3}`)}
                                                                                        className="w-full flex items-center justify-between px-4 py-2 hover:bg-yellow-50 transition-colors"
                                                                                    >
                                                                                        <span className="text-yellow-700">{n3}</span>
                                                                                        <span className="text-xs text-gray-500">{n4s.length} categorias</span>
                                                                                    </button>

                                                                                    {expandedN3[`${n1}-${n2}-${n3}`] && (
                                                                                        <div className="flex flex-wrap gap-2 px-4 py-2 pl-8">
                                                                                            {n4s.map(n4 => (
                                                                                                <span key={n4} className="px-2 py-1 text-xs bg-purple-50 text-purple-700 rounded-full border border-purple-200">
                                                                                                    {n4}
                                                                                                </span>
                                                                                            ))}
                                                                                        </div>
                                                                                    )}
                                                                                </div>
                                                                            ))}
                                                                        </div>
                                                                    )}
                                                                </div>
                                                            ))}
                                                        </div>
                                                    )}
                                                </div>
                                            ))}
                                        </>
                                    )}
                                </div>
                            )}

                            {/* Stats Tab */}
                            {activeTab === 'stats' && (
                                <div className="flex flex-col gap-6 h-full">
                                    {/* Metrics Cards */}
                                    <div className="grid grid-cols-3 gap-4">
                                        <div className="bg-gradient-to-br from-blue-50 to-blue-100 rounded-xl p-5 border border-blue-200">
                                            <p className="text-sm text-blue-600 font-medium">Acurácia</p>
                                            <p className="text-3xl font-bold text-blue-800 flex items-center gap-2">
                                                {modelInfo.metrics.accuracy
                                                    ? `${(modelInfo.metrics.accuracy * 100).toFixed(1)}%`
                                                    : 'N/A'}
                                                {modelInfo.comparison?.metrics && (
                                                    <DiffIndicator
                                                        current={modelInfo.metrics.accuracy || 0}
                                                        previous={modelInfo.comparison.metrics.accuracy}
                                                        isPercent
                                                    />
                                                )}
                                            </p>
                                        </div>
                                        <div className="bg-gradient-to-br from-green-50 to-green-100 rounded-xl p-5 border border-green-200">
                                            <p className="text-sm text-green-600 font-medium">F1 Score</p>
                                            <p className="text-3xl font-bold text-green-800 flex items-center gap-2">
                                                {modelInfo.metrics.f1_macro
                                                    ? `${(modelInfo.metrics.f1_macro * 100).toFixed(1)}%`
                                                    : 'N/A'}
                                                {modelInfo.comparison?.metrics && (
                                                    <DiffIndicator
                                                        current={modelInfo.metrics.f1_macro || 0}
                                                        previous={modelInfo.comparison.metrics.f1_macro || 0}
                                                        isPercent
                                                    />
                                                )}
                                            </p>
                                        </div>
                                        <div className="bg-gradient-to-br from-purple-50 to-purple-100 rounded-xl p-5 border border-purple-200">
                                            <p className="text-sm text-purple-600 font-medium">Descrições Treinadas</p>
                                            <p className="text-3xl font-bold text-purple-800 flex items-center gap-2">
                                                {modelInfo.training_stats.total_descriptions.toLocaleString()}
                                                {modelInfo.comparison?.metrics && (
                                                    <DiffIndicator
                                                        current={modelInfo.training_stats.total_descriptions}
                                                        previous={modelInfo.comparison.metrics.total_samples}
                                                        invert={false}
                                                    />
                                                )}
                                            </p>
                                        </div>
                                    </div>

                                    {/* Top N4 Categories */}
                                    <div className="flex-1 flex flex-col min-h-0">
                                        <h3 className="text-lg font-semibold text-gray-800 mb-4">Top Categorias N4 (por volume de treino)</h3>
                                        <div className="space-y-2 flex-1 overflow-y-auto">
                                            {modelInfo.training_stats.by_n4.map((item, idx) => {
                                                const maxCount = modelInfo.training_stats.by_n4[0]?.count || 1
                                                const percentage = (item.count / maxCount) * 100
                                                return (
                                                    <div key={item.N4} className="flex items-center gap-3">
                                                        <span className="w-6 text-xs text-gray-500 text-right">{idx + 1}.</span>
                                                        <div className="flex-1">
                                                            <div className="flex justify-between text-sm mb-1">
                                                                <span className="font-medium text-gray-700 truncate max-w-[300px]">{item.N4}</span>
                                                                <span className="text-gray-500">{item.count}</span>
                                                            </div>
                                                            <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                                                                <div
                                                                    className="h-full bg-gradient-to-r from-[#14919b] to-[#1B75BB] rounded-full"
                                                                    style={{ width: `${percentage}%` }}
                                                                />
                                                            </div>
                                                        </div>
                                                    </div>
                                                )
                                            })}
                                        </div>
                                    </div>
                                </div>
                            )}

                            {/* Data Tab */}
                            {activeTab === 'data' && (
                                <div className="flex flex-col h-full gap-4">
                                    {/* Actions Bar */}
                                    <div className="flex items-center justify-between gap-4 flex-wrap">
                                        <div className="flex items-center gap-2">
                                            {/* Version Filter */}
                                            <select
                                                value={dataVersionFilter}
                                                onChange={(e) => { setDataVersionFilter(e.target.value); setDataPage(1); }}
                                                className="px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                                            >
                                                <option value="">Todas versões</option>
                                                {dataVersions.map(v => (
                                                    <option key={v} value={v}>{v}</option>
                                                ))}
                                            </select>

                                            <input
                                                type="text"
                                                placeholder="Buscar descrição..."
                                                value={dataSearch}
                                                onChange={(e) => setDataSearch(e.target.value)}
                                                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                                                className="px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#38bec9] w-48"
                                            />
                                            <button onClick={handleSearch} className="px-3 py-2 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg">
                                                Buscar
                                            </button>
                                        </div>

                                        <div className="flex items-center gap-2">
                                            {selectedRows.length > 0 && (
                                                <button
                                                    onClick={handleDeleteSelected}
                                                    disabled={isDeleting}
                                                    className="px-3 py-2 text-sm bg-red-500 text-white rounded-lg hover:bg-red-600 disabled:opacity-50"
                                                >
                                                    Excluir {selectedRows.length} selecionados
                                                </button>
                                            )}

                                            {!selectedVersion.includes('legacy') && modelHistory.length > 1 && (
                                                <button
                                                    onClick={() => handleDeleteVersion(selectedVersion)}
                                                    disabled={isDeleting}
                                                    className="px-3 py-1 text-xs font-medium text-red-600 bg-red-50 hover:bg-red-100 rounded-md transition-colors border border-red-200"
                                                >
                                                    {isDeleting ? 'Excluindo...' : `Excluir versão ${selectedVersion}`}
                                                </button>
                                            )}

                                            {!isSelectedActive && onRestoreModel && selectedVersion && (
                                                <button
                                                    onClick={() => onRestoreModel(selectedVersion)}
                                                    className="px-4 py-2 text-sm bg-[#14919b] text-white rounded-lg hover:bg-[#0e7c86] font-medium"
                                                >
                                                    Restaurar esta versão
                                                </button>
                                            )}
                                        </div>
                                    </div>

                                    {/* Data Table */}
                                    <div className="flex-1 overflow-auto border border-gray-200 rounded-lg">
                                        {isLoadingData ? (
                                            <div className="flex items-center justify-center h-40">
                                                <div className="animate-spin rounded-full h-8 w-8 border-4 border-gray-200 border-t-[#14919b]"></div>
                                            </div>
                                        ) : trainingData.length === 0 ? (
                                            <div className="text-center py-10 text-gray-500">
                                                Nenhum dado encontrado
                                            </div>
                                        ) : (
                                            <table className="min-w-full divide-y divide-gray-200">
                                                <thead className="bg-gray-50 sticky top-0">
                                                    <tr>
                                                        <th className="px-3 py-2 w-10">
                                                            <input
                                                                type="checkbox"
                                                                checked={selectedRows.length === trainingData.length && trainingData.length > 0}
                                                                onChange={toggleSelectAll}
                                                                className="rounded"
                                                            />
                                                        </th>
                                                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Descrição</th>
                                                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">N1</th>
                                                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">N2</th>
                                                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">N3</th>
                                                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">N4</th>
                                                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Versão</th>
                                                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Ocorr.</th>
                                                    </tr>
                                                </thead>
                                                <tbody className="bg-white divide-y divide-gray-100">
                                                    {trainingData.map((row) => (
                                                        <tr key={row.row_id} className="hover:bg-gray-50">
                                                            <td className="px-3 py-2">
                                                                <input
                                                                    type="checkbox"
                                                                    checked={selectedRows.includes(row.row_id)}
                                                                    onChange={() => toggleRowSelection(row.row_id)}
                                                                    className="rounded"
                                                                />
                                                            </td>
                                                            <td className="px-3 py-2 text-sm text-gray-700 max-w-[200px] truncate" title={row.Descrição}>
                                                                {row.Descrição}
                                                            </td>
                                                            <td className="px-3 py-2 text-sm text-gray-700 max-w-[120px] truncate" title={row.N1}>{row.N1}</td>
                                                            <td className="px-3 py-2 text-sm text-gray-700 max-w-[120px] truncate" title={row.N2}>{row.N2}</td>
                                                            <td className="px-3 py-2 text-sm text-gray-700 max-w-[120px] truncate" title={row.N3}>{row.N3}</td>
                                                            <td className="px-3 py-2 text-sm text-gray-700 max-w-[150px] truncate" title={row.N4}>{row.N4}</td>
                                                            <td className="px-3 py-2 text-xs text-gray-500">{row.added_version}</td>
                                                            <td className="px-3 py-2 text-xs text-gray-500 text-center">
                                                                {row.Ocorrências && row.Ocorrências > 1 ? (
                                                                    <span className="px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded-full" title={`${row.Ocorrências} ocorrências`}>
                                                                        {row.Ocorrências}x
                                                                    </span>
                                                                ) : '1'}
                                                            </td>
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        )}
                                    </div>

                                    {/* Pagination */}
                                    <div className="flex items-center justify-between text-sm text-gray-600">
                                        <span>{dataTotal.toLocaleString()} registros</span>
                                        <div className="flex items-center gap-2">
                                            <button
                                                onClick={() => setDataPage(p => Math.max(1, p - 1))}
                                                disabled={dataPage === 1}
                                                className="px-3 py-1 border rounded hover:bg-gray-50 disabled:opacity-50"
                                            >
                                                Anterior
                                            </button>
                                            <span>Página {dataPage} de {dataTotalPages || 1}</span>
                                            <button
                                                onClick={() => setDataPage(p => Math.min(dataTotalPages, p + 1))}
                                                disabled={dataPage >= dataTotalPages}
                                                className="px-3 py-1 border rounded hover:bg-gray-50 disabled:opacity-50"
                                            >
                                                Próxima
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            )}
                        </>
                    )}
                </div>
            </div>
        </div >
    )

    return mounted ? createPortal(content, document.body) : null
}
