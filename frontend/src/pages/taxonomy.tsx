import { useState, useEffect, useRef } from 'react'
import Head from 'next/head'
import { useRouter } from 'next/router'

// Hooks
import { useTaxonomySession, base64ToBlob } from '@/hooks/useTaxonomySession'
import { useCopilot } from '@/hooks/useCopilot'
import { useModelTraining } from '@/hooks/useModelTraining'

// Components
import Tabs from '@/components/ui/Tabs'
import Card from '@/components/ui/Card'
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
    { id: 'train', label: 'Treinar Modelo' },
    { id: 'models', label: 'Gerenciar Modelos' }
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
        setSector,
        setActiveSessionId,
        handleNewUpload,
        handleFileSelect,
        handleClearHistory,
        handleDeleteSession
    } = useTaxonomySession()

    // Copilot chat integration (localStorage persistence is handled internally)
    const {
        copilotMessages,
        chatHistory,
        isCopilotLoading,
        isSending,
        userMessage,
        setUserMessage,
        sendUserMessage,
        generateExecutiveSummary,
        resetChat
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

    // Track which session we've already generated summary for (prevents duplicates)
    const summaryGeneratedForRef = useRef<string | null>(null)

    // Generate executive summary when session is ready (only if no chat exists in localStorage)
    useEffect(() => {
        const currentSessionId = activeSession?.sessionId || null

        // Skip if no session, already loading, or already generated for this session
        if (!currentSessionId || isCopilotLoading || summaryGeneratedForRef.current === currentSessionId) {
            return
        }

        // Check localStorage directly (more reliable than state which may not have loaded yet)
        const storedChat = localStorage.getItem(`pg_spend_chat_${currentSessionId}`)
        const hasExistingChat = storedChat && JSON.parse(storedChat).length > 0

        // Only generate if no chat exists in localStorage
        if (!hasExistingChat) {
            summaryGeneratedForRef.current = currentSessionId
            generateExecutiveSummary()
        }
    }, [activeSession?.sessionId, isCopilotLoading])

    // Load model history when entering models tab
    useEffect(() => {
        if (activeTab === 'models') {
            loadModelHistory(sector)
        }
    }, [activeTab, sector])

    // Auto-scroll to latest message
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

            {/* Fullscreen Processing Overlay */}
            {isProcessing && (
                <div className="fixed inset-0 z-[9999] bg-[#0e0330]/80 backdrop-blur-sm flex items-center justify-center">
                    <div className="flex flex-col items-center justify-center text-center">
                        {/* Spinner */}
                        <div className="w-20 h-20 rounded-full border-4 border-white/20 border-t-[#38bec9] animate-spin"></div>
                        <p className="mt-6 text-lg font-medium text-white">Classificando itens com IA...</p>
                        <p className="mt-2 text-sm text-white/60">Isso pode levar alguns segundos</p>
                    </div>
                </div>
            )}

            {/* Strategic Control Tower Background - Hybrid Theme */}
            <div className="min-h-screen bg-[#F5F7FA] relative overflow-hidden">
                {/* Background Elements - Subtle Light Theme */}
                <div className="absolute inset-0 overflow-hidden pointer-events-none">
                    <div className="absolute top-[-150px] right-[-100px] w-[500px] h-[500px] bg-gradient-to-br from-primary-100/50 to-primary-200/30 rounded-full blur-3xl" />
                    <div className="absolute bottom-[-100px] left-[-50px] w-[400px] h-[400px] bg-gradient-to-tr from-primary-100/40 to-primary-200/20 rounded-full blur-3xl" />
                </div>

                <div className="relative z-10 flex h-screen">
                    {/* Sidebar - Remains Dark */}
                    <SessionSidebar
                        sessions={sessions}
                        activeSessionId={activeSessionId}
                        onSessionSelect={setActiveSessionId}
                        onNewUpload={handleNewUpload}
                        onClearHistory={handleClearHistory}
                        onDeleteSession={handleDeleteSession}
                    />

                    {/* Main Content */}
                    <div className="flex-1 flex flex-col relative z-20">
                        {/* Header - Fixed height with backdrop blur to match sidebar */}
                        <div className="h-[72px] bg-gradient-to-r from-[#2a1177]/95 to-[#1c0957]/95 backdrop-blur-sm border-b border-white/15 px-6 flex items-center justify-between shadow-[0_4px_20px_-4px_rgba(0,0,0,0.5)]">
                            <div className="flex items-center gap-4">
                                <button
                                    onClick={() => router.push('/')}
                                    className="w-10 h-10 rounded-xl bg-white/10 hover:bg-white/15 flex items-center justify-center text-white/80 hover:text-white transition-all border border-white/10 hover:border-white/25 shadow-inner"
                                >
                                    <svg
                                        xmlns="http://www.w3.org/2000/svg"
                                        className="h-5 w-5"
                                        fill="none"
                                        viewBox="0 0 24 24"
                                        stroke="currentColor"
                                        strokeWidth={2}
                                    >
                                        <path
                                            strokeLinecap="round"
                                            strokeLinejoin="round"
                                            d="M10 19l-7-7m0 0l7-7m-7 7h18"
                                        />
                                    </svg>
                                </button>
                                <div>
                                    <h1 className="text-lg font-bold text-white tracking-wide">
                                        Realizar Taxonomia
                                    </h1>
                                    <p className="text-xs text-white/60 font-light">Classificação de gastos com IA</p>
                                </div>
                            </div>

                            {/* AI Status Indicator - Enhanced */}
                            <div className="flex items-center gap-2.5 px-4 py-2 rounded-full bg-[#38bec9]/15 border border-[#38bec9]/30 shadow-[0_0_20px_rgba(56,190,201,0.15)]">
                                <div className="w-2.5 h-2.5 rounded-full bg-[#38bec9] animate-pulse shadow-[0_0_12px_rgba(56,190,201,0.6)]"></div>
                                <span className="text-sm font-medium text-[#38bec9]">Copilot Ativo</span>
                            </div>
                        </div>

                        {/* Content Area */}
                        <div className="flex-1 flex flex-col p-6 min-h-0 overflow-hidden">
                            {!activeSession ? (
                                /* Upload/Training View */
                                <div className="flex-1 flex flex-col items-center justify-center">
                                    <div className="floating-card max-w-5xl w-full p-8 h-[650px] flex flex-col">
                                        {/* Tabs */}
                                        <div className="mb-8 flex-shrink-0">
                                            <Tabs
                                                tabs={TAXONOMY_TABS}
                                                activeTab={activeTab}
                                                onTabChange={(id) => setActiveTab(id as 'classify' | 'train' | 'models')}
                                                disabled={isProcessing || trainingStep === 'training'}
                                            />
                                        </div>

                                        {/* Sector Select */}
                                        <div className="mb-8 flex-shrink-0">
                                            <SectorSelect
                                                value={sector}
                                                onChange={setSector}
                                                sectors={sectors}
                                                disabled={isProcessing || trainingStep === 'training'}
                                                isLoading={isLoadingSectors}
                                            />
                                        </div>

                                        {/* Tab Content - Scrollable Area */}
                                        <div className="flex-1 overflow-y-auto min-h-0 pr-2 custom-scrollbar">
                                            {activeTab === 'classify' && (
                                                <ClassifyTab
                                                    onFileSelect={handleFileSelect}
                                                    isProcessing={isProcessing}
                                                />
                                            )}

                                            {activeTab === 'train' && (
                                                <TrainTab
                                                    sector={sector}
                                                    trainingStep={trainingStep}
                                                    trainingFile={trainingFile}
                                                    previewData={previewData}
                                                    validationStatus={validationStatus}
                                                    trainingResult={trainingResult}
                                                    onFileSelect={handleTrainingFileSelect}
                                                    onConfirmTraining={() => confirmTraining(sector)}
                                                    onCancelTraining={cancelTraining}
                                                />
                                            )}

                                            {activeTab === 'models' && (
                                                <ModelsTab
                                                    sector={sector}
                                                    modelHistory={modelHistory}
                                                    isProcessing={isProcessing}
                                                    onRefresh={() => loadModelHistory(sector)}
                                                    onRestoreModel={(versionId) => handleRestoreModel(sector, versionId)}
                                                />
                                            )}
                                        </div>
                                    </div>
                                </div>
                            ) : (
                                /* Chat View - Floating Card Container */
                                <div className="flex-1 flex flex-col max-w-4xl mx-auto w-full min-h-0">
                                    {/* Chat Header */}
                                    <div className="mb-6 flex items-center justify-between">
                                        <div>
                                            <h3 className="text-lg font-bold text-[#102a43] tracking-wide">
                                                Análise Concluída
                                            </h3>
                                            <p className="text-sm text-gray-500">Converse com a IA sobre os resultados</p>
                                        </div>
                                        <div className="flex items-center gap-3">
                                            <div className="flex items-center gap-2 text-xs text-gray-600 bg-white px-3 py-1.5 rounded-full border border-gray-200 shadow-sm">
                                                <span>Setor:</span>
                                                <span className="font-medium text-[#102a43]">{activeSession.sector}</span>
                                            </div>
                                            <button
                                                onClick={() => setActiveSessionId(null)}
                                                className="p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                                                title="Fechar conversa"
                                            >
                                                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                                                    <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                                                </svg>
                                            </button>
                                        </div>
                                    </div>

                                    {/* Chat Messages Area - Floating Card */}
                                    <div
                                        ref={chatContainerRef}
                                        className="flex-1 overflow-y-auto space-y-6 mb-4 pr-2 min-h-0 p-6 floating-card"
                                    >
                                        {/* Download Card */}
                                        <DownloadCard
                                            downloadUrl={activeSession.downloadUrl!}
                                            downloadFilename={activeSession.downloadFilename!}
                                        />

                                        {/* All Chat Messages (Summary + Interactive) */}
                                        {copilotMessages.map((msg, idx) => (
                                            <ChatMessage key={`msg-${idx}`} message={msg} />
                                        ))}

                                        {/* Loading indicator */}
                                        {(isCopilotLoading || isSending) && <ChatMessageLoading />}
                                    </div>
                                </div>
                            )}

                            {/* Chat Input - Always visible if session active */}
                            {activeSession && (
                                <div className="max-w-5xl mx-auto w-full mt-2">
                                    <ChatInput
                                        value={userMessage}
                                        onChange={setUserMessage}
                                        onSend={sendUserMessage}
                                        disabled={false}
                                        loading={isSending || isCopilotLoading}
                                    />
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div >
        </>
    )
}

// Need to import React for useState
import React from 'react'
