import React, { useState } from 'react'
import ModelViewerOverlay from './ModelViewerOverlay'

interface ModelHistoryEntry {
    version_id: string
    timestamp: string
    filename: string
    status?: string
    metrics: {
        accuracy: number
        f1_macro?: number
    }
}

interface ModelsTabProps {
    sector: string
    modelHistory: ModelHistoryEntry[]
    isProcessing: boolean
    onRefresh: () => void
    onRestoreModel: (versionId: string) => void
}

export default function ModelsTab({
    sector,
    modelHistory,
    isProcessing,
    onRefresh,
    onRestoreModel
}: ModelsTabProps) {
    const [showOverlay, setShowOverlay] = useState(false)

    const activeModel = modelHistory.find(h => h.status === 'active') || modelHistory[0]

    return (
        <>
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 animate-fade-in">
                <div className="flex items-center justify-between mb-6">
                    <div>
                        <h2 className="text-xl font-bold text-gray-800">Biblioteca de Conhecimento - {sector}</h2>
                        <p className="text-sm text-gray-500">Visualize e restaure o histórico de correções manuais do sistema.</p>
                    </div>
                    <button
                        onClick={onRefresh}
                        className="p-2 text-gray-400 hover:text-[#38bec9] transition-colors"
                        title="Atualizar"
                    >
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                        </svg>
                    </button>
                </div>

                {modelHistory.length === 0 ? (
                    <div className="text-center py-12 bg-gray-50 rounded-lg border border-dashed border-gray-300">
                        <svg className="mx-auto h-12 w-12 text-gray-400 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                        </svg>
                        <p className="text-gray-500">Nenhum conhecimento registrado para este setor.</p>
                        <p className="text-sm text-gray-400 mt-1">Suba suas correções na aba "Refinar Inteligência" para registrar o primeiro conhecimento.</p>
                    </div>
                ) : (
                    <div className="bg-gradient-to-br from-gray-50 to-gray-100 rounded-xl p-6 border border-gray-200">
                        <div className="flex items-start justify-between">
                            <div className="flex-1">
                                <div className="flex items-center gap-3 mb-4">
                                    <div className="p-3 bg-green-100 rounded-lg">
                                        <svg className="w-6 h-6 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                                        </svg>
                                    </div>
                                    <div>
                                        <h3 className="text-lg font-semibold text-gray-800">Conhecimento Ativo</h3>
                                        <p className="text-sm text-gray-500">Versão: {activeModel?.version_id}</p>
                                    </div>
                                </div>

                                <div className="grid grid-cols-3 gap-4 mb-4">
                                    <div className="bg-white rounded-lg p-3 border border-gray-200">
                                        <p className="text-xs text-gray-500 mb-1">Acurácia</p>
                                        <p className="text-xl font-bold text-[#14919b]">
                                            {activeModel ? (activeModel.metrics.accuracy * 100).toFixed(1) : '—'}%
                                        </p>
                                    </div>
                                    <div className="bg-white rounded-lg p-3 border border-gray-200">
                                        <p className="text-xs text-gray-500 mb-1">Data do Registro</p>
                                        <p className="text-sm font-medium text-gray-800">
                                            {activeModel ? new Date(activeModel.timestamp).toLocaleDateString('pt-BR') : '—'}
                                        </p>
                                    </div>
                                    <div className="bg-white rounded-lg p-3 border border-gray-200">
                                        <p className="text-xs text-gray-500 mb-1">Versões Disponíveis</p>
                                        <p className="text-xl font-bold text-gray-800">{modelHistory.length}</p>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <button
                            onClick={() => setShowOverlay(true)}
                            className="w-full py-3 px-4 bg-gradient-to-r from-[#38bec9] to-[#14919b] text-white rounded-lg hover:from-[#4dd0d9] hover:to-[#38bec9] transition-all font-medium flex items-center justify-center gap-2 shadow-lg shadow-[#38bec9]/20"
                        >
                            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                            </svg>
                            Visualizar Versões
                        </button>
                    </div>
                )}
            </div>

            {/* Model Viewer Overlay */}
            {showOverlay && (
                <ModelViewerOverlay
                    sector={sector}
                    modelHistory={modelHistory}
                    onClose={() => setShowOverlay(false)}
                    onRestoreModel={(versionId) => {
                        onRestoreModel(versionId)
                        setShowOverlay(false)
                    }}
                    onRefresh={onRefresh}
                />
            )}
        </>
    )
}
