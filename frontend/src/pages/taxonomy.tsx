import React, { useState, useEffect, useRef } from 'react'
import Head from 'next/head'
import { useRouter } from 'next/router'

// Hooks
import { useTaxonomySession } from '@/hooks/useTaxonomySession'
import { useCopilot } from '@/hooks/useCopilot'
import { useModelTraining } from '@/hooks/useModelTraining'

// Components
import Tabs from '@/components/ui/Tabs'
import SessionSidebar from '@/components/taxonomy/SessionSidebar'
import SectorSelect from '@/components/taxonomy/SectorSelect'
import ClassifyTab from '@/components/taxonomy/ClassifyTab'
import TrainTab from '@/components/taxonomy/TrainTab'
import ModelsTab from '@/components/taxonomy/ModelsTab'
import DownloadCard from '@/components/taxonomy/DownloadCard'
import ChatMessage, { ChatMessageLoading } from '@/components/chat/ChatMessage'
import ChatInput from '@/components/chat/ChatInput'

// Tab configuration
const TAXONOMY_TABS = [
    { id: 'classify', label: 'Classificar Itens' },
    { id: 'train', label: 'Refinar Inteligência' },
    { id: 'models', label: 'Biblioteca de Conhecimento' }
]

export default function TaxonomyPage() {
    const router = useRouter()
    const chatContainerRef = useRef<HTMLDivElement>(null)

    // Taxonomy session management
    const {
        sessions,
        activeSessionId,
        activeSession,
        isProcessing,
        sector,
        sectors,
        isLoadingSectors,
        clientContext,
        setSector,
        setClientContext,
        setActiveSessionId,
        handleNewUpload,
        handleFileSelect,
        handleClearHistory,
        handleDeleteSession,
        progress
    } = useTaxonomySession()

    // Local processing state for new tabs
    const [localProcessing, setLocalProcessing] = useState(false)

    // Combined processing state for UI blocking
    const effectiveProcessing = isProcessing || localProcessing

    // Copilot chat integration
    const {
        copilotMessages,
        chatHistory,
        isCopilotLoading,
        isSending,
        userMessage,
        setUserMessage,
        sendUserMessage,
        generateExecutiveSummary
    } = useCopilot({ activeSession })

    // Model training
    const {
        trainingStep,
        trainingFile,
        previewData,
        validationStatus,
        trainingResult,
        modelHistory,
        handleTrainingFileSelect,
        confirmTraining,
        cancelTraining,
        loadModelHistory,
        handleRestoreModel
    } = useModelTraining()

    // Current active tab
    const [activeTab, setActiveTab] = useState<'classify' | 'train' | 'models'>('classify')

    // Track which session we've already generated summary for
    const summaryGeneratedForRef = useRef<string | null>(null)

    // DEBUG: Session monitoring
    useEffect(() => {
        if (activeSession) {
            console.log("------------------------------------------");
            console.log("[DEBUG] ACTIVE SESSION CHANGED:", activeSession.sessionId);
            console.log("[DEBUG] Filename:", activeSession.filename);
            console.log("[DEBUG] Summary Data:", activeSession.summary);
            console.log("[DEBUG] Has Analytics:", !!activeSession.analytics);
            console.log("[DEBUG] Items in session:", activeSession.items?.length || 0);
            console.log("------------------------------------------");
        }
    }, [activeSession?.sessionId])

    // Generate executive summary when session is ready
    useEffect(() => {
        const currentSessionId = activeSession?.sessionId || null

        if (!currentSessionId || isCopilotLoading || summaryGeneratedForRef.current === currentSessionId) {
            return
        }

        const storedChat = localStorage.getItem(`pg_spend_chat_${currentSessionId}`)
        const hasExistingChat = storedChat && JSON.parse(storedChat).length > 0

        if (!hasExistingChat) {
            summaryGeneratedForRef.current = currentSessionId
            generateExecutiveSummary()
        }
    }, [activeSession?.sessionId, isCopilotLoading])

    // Load model history
    useEffect(() => {
        if (activeTab === 'models') {
            loadModelHistory(sector)
        }
    }, [activeTab, sector])

    // Auto-scroll
    useEffect(() => {
        if (chatContainerRef.current) {
            chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight
        }
    }, [chatHistory, copilotMessages, isCopilotLoading, isSending])

    return (
        <>
            <Head>
                <title>Taxonomia - Procurement Garage</title>
            </Head>

            {/* Processing Overlay */}
            {effectiveProcessing && (
                <div className="fixed inset-0 z-[9999] bg-[#0e0330]/90 backdrop-blur-md flex items-center justify-center transition-all duration-500">
                    <div className="flex flex-col items-center justify-center text-center max-w-md w-full px-6">
                        {/* Spinner & Icon */}
                        <div className="relative mb-8">
                            <div className="w-24 h-24 rounded-full border-4 border-white/10 border-t-[#38bec9] animate-spin"></div>
                            <div className="absolute inset-0 flex items-center justify-center">
                                <svg className="w-8 h-8 text-[#38bec9]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
                                </svg>
                            </div>
                        </div>

                        {/* Title */}
                        <h3 className="text-2xl font-bold text-white mb-2 tracking-tight">
                            {progress?.message ? "Analisando Dados..." : "Iniciando IA..."}
                        </h3>

                        {/* Status Message */}
                        <p className="text-white/60 mb-6 font-light h-6 text-sm">
                            {progress?.message || "Preparando ambiente de processamento..."}
                        </p>

                        {/* Progress Bar */}
                        {progress && progress.pct > 0 && (
                            <div className="w-full bg-white/10 rounded-full h-1.5 mb-2 overflow-hidden">
                                <div
                                    className="bg-gradient-to-r from-[#38bec9] to-primary-400 h-1.5 rounded-full transition-all duration-500 ease-out relative"
                                    style={{ width: `${progress.pct}%` }}
                                >
                                    <div className="absolute inset-0 bg-white/30 animate-pulse"></div>
                                </div>
                            </div>
                        )}

                        {/* Percentage Text */}
                        {progress && progress.pct > 0 && (
                            <p className="text-xs font-mono text-[#38bec9] tracking-widest">{progress.pct}% CONCLUÍDO</p>
                        )}

                        {!progress && (
                            <p className="text-xs text-white/40 animate-pulse mt-4">Conectando ao worker assíncrono...</p>
                        )}
                    </div>
                </div>
            )}

            <div className="min-h-screen bg-[#F5F7FA] relative overflow-hidden">
                <div className="absolute inset-0 overflow-hidden pointer-events-none">
                    <div className="absolute top-[-150px] right-[-100px] w-[500px] h-[500px] bg-gradient-to-br from-primary-100/50 to-primary-200/30 rounded-full blur-3xl" />
                    <div className="absolute bottom-[-100px] left-[-50px] w-[400px] h-[400px] bg-gradient-to-tr from-primary-100/40 to-primary-200/20 rounded-full blur-3xl" />
                </div>

                <div className="relative z-10 flex h-screen">
                    <SessionSidebar
                        sessions={sessions}
                        activeSessionId={activeSessionId}
                        onSessionSelect={setActiveSessionId}
                        onNewUpload={handleNewUpload}
                        onClearHistory={handleClearHistory}
                        onDeleteSession={handleDeleteSession}
                    />

                    <div className="flex-1 flex flex-col relative z-20">
                        {/* Header */}
                        <div className="h-[72px] bg-gradient-to-r from-[#2a1177]/95 to-[#1c0957]/95 backdrop-blur-sm border-b border-white/15 px-6 flex items-center justify-between shadow-lg">
                            <div className="flex items-center gap-4">
                                <button
                                    onClick={() => router.push('/')}
                                    className="w-10 h-10 rounded-xl bg-white/10 hover:bg-white/15 flex items-center justify-center text-white/80 hover:text-white transition-all border border-white/10"
                                >
                                    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                                    </svg>
                                </button>
                                <div>
                                    <h1 className="text-lg font-bold text-white tracking-wide">Realizar Taxonomia</h1>
                                    <p className="text-xs text-white/60 font-light">Classificação de gastos com IA</p>
                                </div>
                            </div>
                            <div className="flex items-center gap-2.5 px-4 py-2 rounded-full bg-[#38bec9]/15 border border-[#38bec9]/30">
                                <div className="w-2.5 h-2.5 rounded-full bg-[#38bec9] animate-pulse"></div>
                                <span className="text-sm font-medium text-[#38bec9]">Copilot Ativo</span>
                            </div>
                        </div>

                        {/* Content Area */}
                        <div className="flex-1 flex flex-col p-6 min-h-0 overflow-hidden">
                            {!activeSession ? (
                                <div className="flex-1 flex flex-col items-center justify-center">
                                    <div className="floating-card max-w-5xl w-full p-8 h-[650px] flex flex-col bg-white rounded-3xl shadow-xl overflow-hidden">
                                        <div className="mb-8 flex-shrink-0">
                                            <Tabs
                                                tabs={TAXONOMY_TABS}
                                                activeTab={activeTab}
                                                onTabChange={(id) => setActiveTab(id as any)}
                                                disabled={effectiveProcessing}
                                            />
                                        </div>

                                        <div className="mb-8 flex-shrink-0">
                                            <SectorSelect
                                                value={sector}
                                                onChange={setSector}
                                                sectors={sectors}
                                                disabled={effectiveProcessing}
                                                isLoading={isLoadingSectors}
                                            />
                                        </div>

                                        {/* Client Context Input */}
                                        {activeTab === 'classify' && (
                                            <div className="mb-8 flex-shrink-0 animate-fadeIn">
                                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                                    Contexto do Cliente e Regras de Negócio (Opcional)
                                                </label>
                                                <input
                                                    type="text"
                                                    value={clientContext}
                                                    onChange={(e) => setClientContext(e.target.value)}
                                                    placeholder='Escreva aqui o prompt detalhado para categorização...'
                                                    className="w-full border border-gray-200 bg-white rounded-xl px-4 py-3 text-base text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 transition-all shadow-sm placeholder:text-gray-400"
                                                    disabled={effectiveProcessing}
                                                />
                                                <p className="mt-1.5 text-[10px] text-gray-400 italic">
                                                    * O contexto ajuda a IA a decidir categorias ambíguas (ex: Ar Condicionado em Escola vs Indústria).
                                                </p>
                                            </div>
                                        )}

                                        <div className="flex-1 overflow-y-auto min-h-0 pr-2 custom-scrollbar">
                                            {activeTab === 'classify' && <ClassifyTab onFileSelect={handleFileSelect} isProcessing={effectiveProcessing} />}
                                            {activeTab === 'train' && (
                                                <TrainTab
                                                    sector={sector}
                                                    trainingStep={trainingStep}
                                                    trainingFile={trainingFile}
                                                    previewData={previewData}
                                                    validationStatus={validationStatus}
                                                    trainingResult={trainingResult}
                                                    onFileSelect={(file, content) => handleTrainingFileSelect(file, content, sector)}
                                                    onConfirmTraining={() => confirmTraining(sector)}
                                                    onCancelTraining={cancelTraining}
                                                />
                                            )}
                                            {activeTab === 'models' && (
                                                <ModelsTab
                                                    sector={sector}
                                                    modelHistory={modelHistory}
                                                    isProcessing={effectiveProcessing}
                                                    onRefresh={() => loadModelHistory(sector)}
                                                    onRestoreModel={(versionId) => handleRestoreModel(sector, versionId)}
                                                />
                                            )}
                                        </div>
                                    </div>
                                </div>
                            ) : (
                                <div className="flex-1 flex flex-col max-w-4xl mx-auto w-full min-h-0">
                                    {/* Chat Header */}
                                    <div className="mb-4 flex items-center justify-between px-4">
                                        <div className="flex-1 min-w-0">
                                            <h3 className="text-xl font-bold text-[#102a43] truncate">
                                                Análise Concluída
                                                <span className="ml-2 text-[10px] bg-sky-50 text-sky-500 border border-sky-100 px-1.5 py-0.5 rounded uppercase font-mono tracking-tighter">v2.5-final</span>
                                            </h3>
                                            <div className="flex items-center gap-2 mt-1">
                                                <div className="flex items-center gap-2 text-xs text-gray-600 bg-white px-3 py-1 rounded-full border border-gray-200">
                                                    <span>Setor:</span>
                                                    <span className="font-medium text-[#102a43]">{activeSession.sector}</span>
                                                </div>
                                                <button
                                                    onClick={() => setActiveSessionId(null)}
                                                    className="p-1 text-gray-400 hover:text-red-500 transition-colors"
                                                >
                                                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                                                        <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                                                    </svg>
                                                </button>
                                            </div>
                                        </div>
                                    </div>

                                    {/* Metrics Diagnostic (Hidden by default, will show if summary fails) */}
                                    {(!copilotMessages.length && !isCopilotLoading) && (
                                        <div className="mb-4 bg-orange-50 border border-orange-100 rounded-xl p-4 flex items-center justify-between">
                                            <div className="flex items-center gap-3">
                                                <svg className="w-5 h-5 text-orange-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                                </svg>
                                                <div>
                                                    <p className="text-xs font-bold text-orange-800">Diagnóstico de Dados</p>
                                                    <p className="text-[10px] text-orange-600">
                                                        Itens: {activeSession.summary?.total_linhas || 0} |
                                                        Download: {activeSession.fileContentBase64 ? 'OK' : 'PENDENTE'} |
                                                        Copilot: {activeSession.analytics ? 'PRONTO' : 'ERRO'}
                                                    </p>
                                                </div>
                                            </div>
                                            <button
                                                onClick={() => generateExecutiveSummary()}
                                                className="text-[10px] bg-white border border-orange-200 px-3 py-1 rounded-lg text-orange-700 font-bold hover:bg-orange-100"
                                            >
                                                FORÇAR RESUMO
                                            </button>
                                        </div>
                                    )}

                                    {/* Messages Area */}
                                    <div ref={chatContainerRef} className="flex-1 overflow-y-auto space-y-6 mb-4 pr-2 min-h-0 p-6 floating-card bg-white rounded-3xl shadow-sm border border-gray-100">
                                        {activeSession.fileContentBase64 && activeSession.downloadFilename && (
                                            <DownloadCard fileContentBase64={activeSession.fileContentBase64} downloadFilename={activeSession.downloadFilename} />
                                        )}

                                        {copilotMessages.length > 0 ? (
                                            copilotMessages.map((msg, idx) => <ChatMessage key={`msg-${idx}`} message={msg} />)
                                        ) : !isCopilotLoading && (
                                            <div className="flex flex-col items-center justify-center py-20 opacity-40">
                                                <svg className="w-12 h-12 text-[#102a43] mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                                                </svg>
                                                <p className="text-sm">Envie uma mensagem ou aguarde o resumo...</p>
                                            </div>
                                        )}

                                        {(isCopilotLoading || isSending) && <ChatMessageLoading />}
                                    </div>

                                    {/* Input Area */}
                                    <div className="w-full mt-2">
                                        <ChatInput
                                            value={userMessage}
                                            onChange={setUserMessage}
                                            onSend={sendUserMessage}
                                            disabled={false}
                                            loading={isSending || isCopilotLoading}
                                        />
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </>
    )
}