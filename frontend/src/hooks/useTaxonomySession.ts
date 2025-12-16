import { useState, useCallback, useEffect } from 'react'
import { apiClient } from '@/lib/api'
import * as XLSX from 'xlsx'
import { saveSession, getAllSessions, clearAllSessions, deleteSession } from '@/lib/database'

export interface TaxonomySession {
    sessionId: string
    filename: string
    sector: string
    timestamp: string
    summary?: any
    analytics?: any
    items?: any[]
    downloadUrl?: string // Runtime only (blob URLs can't be persisted)
    downloadFilename?: string
    fileContentBase64?: string // Persisted for re-creating download
}

interface UseTaxonomySessionReturn {
    // State
    sessions: TaxonomySession[]
    activeSessionId: string | null
    activeSession: TaxonomySession | undefined
    isProcessing: boolean
    sector: string
    sectors: string[]
    isLoadingSectors: boolean

    // Actions
    setSector: (sector: string) => void
    setActiveSessionId: (id: string | null) => void
    handleNewUpload: () => void
    handleFileSelect: (file: File, fileContent: string, hierarchyContent?: string) => Promise<void>
    handleCreateDiscoverySession: (clusterCount: number) => Promise<void>
    handleClearHistory: () => void
    handleDeleteSession: (sessionId: string) => void
}

export function useTaxonomySession(): UseTaxonomySessionReturn {
    const [sessions, setSessions] = useState<TaxonomySession[]>([])
    const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
    const [isProcessing, setIsProcessing] = useState(false)
    const [sector, setSector] = useState('Varejo')
    const [sectors, setSectors] = useState<string[]>([])
    const [isLoadingSectors, setIsLoadingSectors] = useState(true)

    const activeSession = sessions.find(s => s.sessionId === activeSessionId)

    // Load sessions from IndexedDB on mount
    useEffect(() => {
        const loadSessions = async () => {
            const storedSessions = await getAllSessions()
            if (storedSessions.length > 0) {
                // Recreate blob URLs for download
                const sessionsWithUrls = storedSessions.map(session => {
                    if (session.fileContentBase64) {
                        const blob = base64ToBlob(
                            session.fileContentBase64,
                            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                        )
                        return { ...session, downloadUrl: URL.createObjectURL(blob) }
                    }
                    return session
                })
                setSessions(sessionsWithUrls)
            }
        }
        loadSessions()
    }, [])

    // Load sectors from Spend_Taxonomy.xlsx
    useEffect(() => {
        const loadSectors = async () => {
            try {
                setIsLoadingSectors(true)
                const response = await fetch('/Spend_Taxonomy.xlsx')
                const arrayBuffer = await response.arrayBuffer()
                const workbook = XLSX.read(arrayBuffer, { type: 'array' })

                // Find CONFIG sheet
                const configSheetName = workbook.SheetNames.find(name => name.toUpperCase().includes('CONFIG')) || workbook.SheetNames[0]
                const worksheet = workbook.Sheets[configSheetName]

                const jsonData: any[] = XLSX.utils.sheet_to_json(worksheet)

                // Extract and filter sectors
                const loadedSectors = jsonData
                    .map((row: any) => row.Setor)
                    .filter((s: any) =>
                        s &&
                        typeof s === 'string' &&
                        s.trim().length > 0 &&
                        s.length < 30 &&
                        !s.toLowerCase().includes('essa aba diz')
                    )

                const uniqueSectors = Array.from(new Set(loadedSectors)) as string[]

                if (uniqueSectors.length > 0) {
                    setSectors(uniqueSectors)
                    if (!uniqueSectors.includes(sector)) {
                        setSector(uniqueSectors[0])
                    }
                } else {
                    setSectors(['Varejo', 'Educacional'])
                }

            } catch (error) {
                console.error("Error loading sectors:", error)
                setSectors(['Varejo', 'Educacional'])
            } finally {
                setIsLoadingSectors(false)
            }
        }

        loadSectors()
    }, [])

    const handleNewUpload = useCallback(() => {
        setActiveSessionId(null)
    }, [])

    // Helper function to convert base64 to Blob
    const base64ToBlob = (base64: string, contentType: string): Blob => {
        const byteCharacters = atob(base64)
        const byteNumbers = new Array(byteCharacters.length)
        for (let i = 0; i < byteCharacters.length; i++) {
            byteNumbers[i] = byteCharacters.charCodeAt(i)
        }
        const byteArray = new Uint8Array(byteNumbers)
        return new Blob([byteArray], { type: contentType })
    }

    const handleFileSelect = async (file: File, fileContent: string, hierarchyContent?: string) => {
        setIsProcessing(true)

        try {
            const dictionaryResponse = await fetch('/Spend_Taxonomy.xlsx')
            const dictionaryBlob = await dictionaryResponse.blob()

            const reader = new FileReader()
            reader.onload = async (e) => {
                const dictionaryBase64 = (e.target?.result as string).split(',')[1]

                // Process file via Azure Function (include custom hierarchy if provided)
                const result = await apiClient.processTaxonomy(
                    fileContent,
                    dictionaryBase64,
                    sector,
                    file.name,
                    hierarchyContent
                )

                // Generate XLSX file for download
                const xlsxBlob = base64ToBlob(result.fileContent, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                const downloadUrl = URL.createObjectURL(xlsxBlob)

                // Create new session object
                const newSession: TaxonomySession = {
                    filename: file.name,
                    sector: sector,
                    sessionId: result.sessionId,
                    summary: result.summary,
                    analytics: result.analytics,
                    items: result.items,
                    downloadUrl: downloadUrl,
                    downloadFilename: result.filename,
                    timestamp: new Date().toISOString()
                }

                // Add to sessions array and set as active
                setSessions(prev => [newSession, ...prev])
                setActiveSessionId(result.sessionId)

                // Persist to IndexedDB (include fileContent for later re-download)
                const sessionToSave = {
                    ...newSession,
                    downloadUrl: undefined, // Don't persist blob URL
                    fileContentBase64: result.fileContent
                }
                saveSession(sessionToSave)

                setIsProcessing(false)
            }
            reader.readAsDataURL(dictionaryBlob)

        } catch (error) {
            console.error('Error processing file:', error)
            setIsProcessing(false)
            alert('Erro ao processar arquivo. Tente novamente.')
        }
    }

    const handleClearHistory = useCallback(async () => {
        // Clear IndexedDB
        await clearAllSessions()

        // Clear localStorage chat entries
        const keysToRemove: string[] = []
        for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i)
            if (key?.startsWith('pg_spend_chat_')) {
                keysToRemove.push(key)
            }
        }
        keysToRemove.forEach(key => localStorage.removeItem(key))

        // Clear React state
        setSessions([])
        setActiveSessionId(null)
    }, [])

    const handleDeleteSession = useCallback(async (sessionId: string) => {
        // Delete from IndexedDB
        await deleteSession(sessionId)

        // Delete from localStorage
        localStorage.removeItem(`pg_spend_chat_${sessionId}`)

        // Update React state
        setSessions(prev => prev.filter(s => s.sessionId !== sessionId))

        // If deleting the active session, clear selection
        if (activeSessionId === sessionId) {
            setActiveSessionId(null)
        }
    }, [activeSessionId])

    const handleCreateDiscoverySession = useCallback(async (clusterCount: number) => {
        const sessionId = `discovery-${Date.now()}`
        const newSession: TaxonomySession = {
            sessionId,
            filename: `Descoberta de Padrões (${clusterCount} grupos)`,
            sector: sector,
            timestamp: new Date().toISOString(),
            // No download URL initially for discovery sessions
        }

        setSessions(prev => [newSession, ...prev])
        setActiveSessionId(sessionId)

        // Persist
        await saveSession(newSession)
    }, [sector])

    return {
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
        handleCreateDiscoverySession,
        handleClearHistory,
        handleDeleteSession
    }
}

// Export base64ToBlob for use in other components
export const base64ToBlob = (base64: string, contentType: string): Blob => {
    const byteCharacters = atob(base64)
    const byteNumbers = new Array(byteCharacters.length)
    for (let i = 0; i < byteCharacters.length; i++) {
        byteNumbers[i] = byteCharacters.charCodeAt(i)
    }
    const byteArray = new Uint8Array(byteNumbers)
    return new Blob([byteArray], { type: contentType })
}
