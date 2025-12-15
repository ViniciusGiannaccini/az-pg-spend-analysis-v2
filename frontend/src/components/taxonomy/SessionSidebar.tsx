import React from 'react'
import { colors, tw } from '@/lib/design-tokens'

export interface Session {
    sessionId: string
    filename: string
    sector: string
    timestamp: string
    summary?: any
    analytics?: any
    items?: any[]
    downloadUrl?: string
    downloadFilename?: string
}

interface SessionSidebarProps {
    sessions: Session[]
    activeSessionId: string | null
    onSessionSelect: (sessionId: string) => void
    onNewUpload: () => void
    onClearHistory?: () => void
    onDeleteSession?: (sessionId: string) => void
}

export default function SessionSidebar({
    sessions,
    activeSessionId,
    onSessionSelect,
    onNewUpload,
    onClearHistory,
    onDeleteSession
}: SessionSidebarProps) {
    return (
        <div className="w-72 bg-gradient-to-b from-[#1c0957] via-[#180847] to-[#120535] border-r border-white/10 flex flex-col h-full shrink-0 relative z-30 shadow-2xl">
            {/* Logo Area - Fixed height to align with main header */}
            <div className="h-[72px] px-6 flex items-center border-b border-white/15 bg-[#1c0957]/80 backdrop-blur-sm shadow-[0_4px_20px_-4px_rgba(0,0,0,0.4)]">
                <div className="flex items-center gap-3 h-10">
                    <div className="w-2.5 h-2.5 rounded-full bg-[#38bec9] shadow-[0_0_12px_rgba(56,190,201,0.6)] animate-pulse" />
                    <span className="font-bold tracking-tight text-white">HISTÓRICO</span>
                </div>
            </div>

            {/* Sessions List - Inset visual effect */}
            <div className="flex-1 overflow-y-auto py-4 px-3 space-y-2 custom-scrollbar bg-gradient-to-b from-transparent via-white/[0.02] to-transparent">
                {sessions.length === 0 ? (
                    <div className="text-center py-10 px-4">
                        <div className="w-14 h-14 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center mx-auto mb-4 text-white/20 shadow-inner">
                            <svg xmlns="http://www.w3.org/2000/svg" className="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                            </svg>
                        </div>
                        <p className="text-sm text-white/50 font-medium">Nenhuma sessão recente</p>
                        <p className="text-xs text-white/30 mt-1">Faça upload para começar</p>
                    </div>
                ) : (
                    sessions.map((session) => (
                        <SessionItem
                            key={session.sessionId}
                            session={session}
                            isActive={session.sessionId === activeSessionId}
                            onClick={() => onSessionSelect(session.sessionId)}
                            onDelete={onDeleteSession ? () => onDeleteSession(session.sessionId) : undefined}
                        />
                    ))
                )}
            </div>

            {/* Footer Actions - Elevated with top shadow */}
            <div className="p-4 border-t border-white/15 bg-[#1c0957]/90 backdrop-blur-sm shadow-[0_-4px_20px_-4px_rgba(0,0,0,0.4)]">
                <button
                    onClick={onNewUpload}
                    className="w-full h-11 flex items-center justify-center gap-2 bg-gradient-to-r from-[#38bec9] to-[#14919b] hover:from-[#4dd0d9] hover:to-[#38bec9] text-white rounded-xl font-medium shadow-lg shadow-[#38bec9]/20 hover:shadow-[#38bec9]/40 transition-all duration-300 mb-3 group"
                >
                    <svg
                        xmlns="http://www.w3.org/2000/svg"
                        className="h-5 w-5 group-hover:scale-110 transition-transform"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                    >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                    </svg>
                    <span>Nova Taxonomia</span>
                </button>

                {onClearHistory && (
                    <button
                        onClick={onClearHistory}
                        className="w-full flex items-center justify-center gap-2 py-2.5 text-xs text-white/30 hover:text-white/60 hover:bg-white/5 rounded-lg transition-colors border border-transparent hover:border-white/5"
                    >
                        <svg
                            xmlns="http://www.w3.org/2000/svg"
                            className="h-4 w-4"
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                        >
                            <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={1.5}
                                d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                            />
                        </svg>
                        Limpar Histórico
                    </button>
                )}
            </div>
        </div>
    )
}

function EmptyState() {
    return (
        <div className="text-center py-16 px-4">
            <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-white/5 flex items-center justify-center">
                <svg className="w-8 h-8 text-white/30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
            </div>
            <p className="text-sm font-medium text-white/60 mb-1">Nenhuma sessão recente</p>
            <p className="text-xs text-white/40">Faça o upload de um arquivo para iniciar.</p>
        </div>
    )
}

interface SessionItemProps {
    session: Session
    isActive: boolean
    onClick: () => void
    onDelete?: () => void
}

function SessionItem({ session, isActive, onClick, onDelete }: SessionItemProps) {
    const handleDelete = (e: React.MouseEvent) => {
        e.stopPropagation() // Prevent selecting the session
        if (onDelete) onDelete()
    }

    return (
        <button
            onClick={onClick}
            className={`w-full text-left p-3 rounded-xl transition-all duration-200 group relative ${isActive
                ? 'bg-white/15 backdrop-blur-sm border-l-2 border-[#38bec9]'
                : 'hover:bg-white/10 border-l-2 border-transparent'
                }`}
        >
            <div className="flex items-start gap-3">
                {/* File Icon */}
                <div className={`mt-0.5 p-2 rounded-lg transition-colors ${isActive
                    ? 'bg-[#38bec9]/20 text-[#38bec9]'
                    : 'bg-white/10 text-white/50 group-hover:text-white/70'
                    }`}>
                    <svg
                        className="w-4 h-4"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                    >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                    <p className={`text-sm font-medium truncate transition-colors ${isActive ? 'text-white' : 'text-white/80 group-hover:text-white'
                        }`}>
                        {session.filename}
                    </p>
                    <p className={`text-xs mt-0.5 ${isActive ? 'text-[#38bec9]' : 'text-white/50'
                        }`}>
                        {session.sector}
                    </p>
                    <p className="text-xs text-white/40 mt-1">
                        {new Date(session.timestamp).toLocaleString('pt-BR', {
                            day: '2-digit',
                            month: '2-digit',
                            hour: '2-digit',
                            minute: '2-digit'
                        })}
                    </p>
                </div>

                {/* Active Indicator */}
                {isActive && (
                    <div className="w-2 h-2 rounded-full bg-[#38bec9] animate-pulse mt-2"></div>
                )}
            </div>

            {/* Delete Button - Bottom Right */}
            {onDelete && (
                <div
                    onClick={handleDelete}
                    className="absolute bottom-2 right-2 p-1.5 rounded-lg opacity-0 group-hover:opacity-100 hover:bg-red-500/20 text-white/40 hover:text-red-300 transition-all cursor-pointer"
                    title="Excluir sessão"
                >
                    <svg
                        className="w-3.5 h-3.5"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                    >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                </div>
            )}
        </button>
    )
}
