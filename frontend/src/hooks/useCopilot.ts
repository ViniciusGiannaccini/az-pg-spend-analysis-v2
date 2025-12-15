import { useState, useCallback, useEffect } from 'react'
import { apiClient } from '@/lib/api'
import { generateSmartContext, formatSmartContextMessage } from '@/lib/smart-context'
import type { Message } from '@/components/chat/ChatMessage'

// ============================================
// LocalStorage Utilities
// ============================================
const STORAGE_PREFIX = 'pg_spend_chat_'

const getChatFromStorage = (sessionId: string): Message[] => {
    if (typeof window === 'undefined') return []
    try {
        const stored = localStorage.getItem(`${STORAGE_PREFIX}${sessionId}`)
        if (!stored) return []
        const parsed = JSON.parse(stored)
        // Convert timestamp strings back to Date objects
        return parsed.map((msg: any) => ({
            ...msg,
            timestamp: new Date(msg.timestamp)
        }))
    } catch {
        return []
    }
}

const saveChatToStorage = (sessionId: string, messages: Message[]) => {
    if (typeof window === 'undefined') return
    try {
        localStorage.setItem(`${STORAGE_PREFIX}${sessionId}`, JSON.stringify(messages))
    } catch (e) {
        console.warn('Failed to save chat to localStorage', e)
    }
}

// ============================================
// Hook Interface
// ============================================
interface UseCopilotProps {
    activeSession: any | null
}

interface UseCopilotReturn {
    copilotMessages: Message[]
    chatHistory: Message[]
    isCopilotLoading: boolean
    isSending: boolean
    userMessage: string
    setUserMessage: (msg: string) => void
    sendUserMessage: () => Promise<void>
    generateExecutiveSummary: () => Promise<void>
    resetChat: () => void
}

// ============================================
// Main Hook
// ============================================
export function useCopilot({ activeSession }: UseCopilotProps): UseCopilotReturn {
    const sessionId = activeSession?.sessionId || null

    // State - initialized from localStorage
    const [copilotMessages, setCopilotMessages] = useState<Message[]>([])
    const [chatHistory, setChatHistory] = useState<Message[]>([])
    const [isCopilotLoading, setIsCopilotLoading] = useState(false)
    const [isSending, setIsSending] = useState(false)
    const [userMessage, setUserMessage] = useState('')

    // Load chat from localStorage when session changes
    useEffect(() => {
        if (sessionId) {
            const stored = getChatFromStorage(sessionId)
            setCopilotMessages(stored)
            setChatHistory(stored)
        } else {
            setCopilotMessages([])
            setChatHistory([])
        }
    }, [sessionId])

    // Helper: Save messages and update state
    const updateMessages = useCallback((newMessages: Message[]) => {
        setCopilotMessages(newMessages)
        setChatHistory(newMessages)
        if (sessionId) {
            saveChatToStorage(sessionId, newMessages)
        }
    }, [sessionId])

    const resetChat = useCallback(() => {
        setIsCopilotLoading(false)
        setIsSending(false)
        setUserMessage('')
    }, [])

    // Execute a conversation turn (stateless RAG)
    const executeConversationTurn = async (userMsg: string, contextData: any): Promise<Message[]> => {
        try {
            const tokenData = await apiClient.getDirectLineToken()
            const tempConversationId = tokenData.conversationId
            const tempToken = tokenData.token

            const finalMessage = formatSmartContextMessage(userMsg, contextData)

            await apiClient.postActivity(tempConversationId, tempToken, {
                type: 'message',
                from: { id: 'user' },
                text: finalMessage,
                locale: 'pt-BR'
            })

            let attempts = 0
            const maxAttempts = 12

            const poll = async (): Promise<Message[]> => {
                if (attempts >= maxAttempts) return []
                attempts++

                try {
                    const activityData = await apiClient.getMessagesFromCopilot(tempConversationId, tempToken)

                    const botMsgs = activityData.activities?.filter((a: any) =>
                        (a.from?.id !== 'user' && a.from.name !== 'user') &&
                        a.type === 'message' &&
                        a.text
                    ).map((msg: any) => ({
                        from: 'bot' as const,
                        text: msg.text.replace(/(?:📊|✅)?\s*AI-generated content may be incorrect[.\s]*/gi, '').trim(),
                        timestamp: new Date(msg.timestamp)
                    })) || []

                    if (botMsgs.length > 0) return botMsgs

                    await new Promise(r => setTimeout(r, 5000))
                    return poll()
                } catch (e) {
                    console.error("Poll error", e)
                    return []
                }
            }

            return poll()
        } catch (error) {
            console.error("Turn error", error)
            return [{ from: 'bot', text: "Erro ao processar mensagem. Tente novamente.", timestamp: new Date() }]
        }
    }

    // Execute a direct message without Smart Context wrapper (fallback for greetings/casual)
    const executeDirectMessage = async (userMsg: string): Promise<Message[]> => {
        try {
            const tokenData = await apiClient.getDirectLineToken()
            const tempConversationId = tokenData.conversationId
            const tempToken = tokenData.token

            // Send message with Portuguese instruction (no JSON context)
            await apiClient.postActivity(tempConversationId, tempToken, {
                type: 'message',
                from: { id: 'user' },
                text: `Responda em português do Brasil: ${userMsg}`,
                locale: 'pt-BR'
            })

            let attempts = 0
            const maxAttempts = 12

            const poll = async (): Promise<Message[]> => {
                if (attempts >= maxAttempts) return []
                attempts++

                try {
                    const activityData = await apiClient.getMessagesFromCopilot(tempConversationId, tempToken)

                    const botMsgs = activityData.activities?.filter((a: any) =>
                        (a.from?.id !== 'user' && a.from.name !== 'user') &&
                        a.type === 'message' &&
                        a.text
                    ).map((msg: any) => ({
                        from: 'bot' as const,
                        text: msg.text.replace(/(?:📊|✅)?\s*AI-generated content may be incorrect[.\s]*/gi, '').trim(),
                        timestamp: new Date(msg.timestamp)
                    })) || []

                    if (botMsgs.length > 0) return botMsgs

                    await new Promise(r => setTimeout(r, 5000))
                    return poll()
                } catch (e) {
                    console.error("Poll error", e)
                    return []
                }
            }

            return poll()
        } catch (error) {
            console.error("Direct message error", error)
            return [{ from: 'bot', text: "Erro ao processar mensagem. Tente novamente.", timestamp: new Date() }]
        }
    }

    const sendUserMessage = async () => {
        if (!userMessage.trim() || !sessionId) return

        const currentMsg = userMessage
        setUserMessage('')
        setIsSending(true)

        // Add user message immediately
        const userMsgObj: Message = { from: 'user', text: currentMsg, timestamp: new Date() }
        const updatedWithUser = [...copilotMessages, userMsgObj]
        updateMessages(updatedWithUser)

        try {
            const smartContext = generateSmartContext(currentMsg, activeSession?.items || [])

            // If smart context found a match, use it; otherwise send message directly (fallback)
            if (smartContext) {
                // Has context - use structured prompt
                const responses = await executeConversationTurn(currentMsg, smartContext)
                updateMessages([...updatedWithUser, ...responses])
            } else {
                // No context (greeting, casual conversation) - send message directly
                const responses = await executeDirectMessage(currentMsg)
                updateMessages([...updatedWithUser, ...responses])
            }
        } catch (err) {
            console.error(err)
        } finally {
            setIsSending(false)
        }
    }

    const generateExecutiveSummary = async () => {
        if (!activeSession || !sessionId) return

        const hasValidSummary = activeSession.summary?.total_linhas > 0
        const hasValidAnalytics = activeSession.analytics?.pareto && activeSession.analytics.pareto.length > 0

        if (!hasValidSummary || !hasValidAnalytics) return

        setIsCopilotLoading(true)

        try {
            const tokenData = await apiClient.getDirectLineToken()
            const tempConversationId = tokenData.conversationId
            const tempToken = tokenData.token

            const totalItems = activeSession.summary?.total_linhas || 0
            const uniqueItems = activeSession.summary?.unico || 0
            const ambiguousItems = activeSession.summary?.ambiguo || 0
            const classifiedItems = uniqueItems + ambiguousItems
            const classificationRate = totalItems ? ((classifiedItems / totalItems) * 100).toFixed(1) : '0.0'
            const uniqueRate = totalItems ? ((uniqueItems / totalItems) * 100).toFixed(1) : '0.0'
            const ambiguousRate = totalItems ? ((ambiguousItems / totalItems) * 100).toFixed(1) : '0.0'

            const contextData = {
                metricas_gerais: {
                    total_itens: totalItems,
                    itens_classificados: classifiedItems,
                    taxa_classificacao: `${classificationRate}%`,
                    unicos_classificados: uniqueItems,
                    taxa_unicos: `${uniqueRate}%`,
                    ambiguos_classificados: ambiguousItems,
                    taxa_ambiguos: `${ambiguousRate}%`
                },
                top_N4_Categorias: activeSession.analytics?.pareto_N4?.slice(0, 20).map((item: any) => ({
                    categoria: item.N4,
                    volume: item.Contagem
                })),
            }

            const summaryPrompt = `ATUE COMO UM ANALISTA DE DADOS SÊNIOR.
Sua tarefa é analisar os dados JSON fornecidos abaixo e gerar um RESUMO EXECUTIVO.

INSTRUÇÕES OBRIGATÓRIAS:
1. Analise os dados fornecidos nesta mensagem. NÃO peça mais informações.
2. O foco principal deve ser as estatísticas de 'metricas_gerais' e os rankings de 'top_N4'.
3. Responda em Português do Brasil com formatação profissional (Markdown).

DADOS DA ANÁLISE(JSON):
\`\`\`json
${JSON.stringify(contextData, null, 2)}
\`\`\``

            await apiClient.sendMessageToCopilot(tempConversationId, tempToken, summaryPrompt)

            let attempts = 0
            const maxAttempts = 15
            let pollingComplete = false // Guard to prevent duplicate updates

            const poll = async () => {
                if (attempts >= maxAttempts || pollingComplete) {
                    setIsCopilotLoading(false)
                    return
                }
                attempts++

                try {
                    const activityData = await apiClient.getMessagesFromCopilot(tempConversationId, tempToken)

                    const botMsgs = activityData.activities?.filter((a: any) =>
                        (a.from?.id !== 'user' && a.from.name !== 'user') &&
                        a.type === 'message' &&
                        a.text
                    ).map((msg: any) => ({
                        from: 'bot' as const,
                        text: msg.text.replace(/(?:📊|✅)?\s*AI-generated content may be incorrect[.\s]*/gi, '').trim(),
                        timestamp: new Date(msg.timestamp)
                    })) || []

                    if (botMsgs.length > 0 && !pollingComplete) {
                        pollingComplete = true // Mark complete BEFORE updating
                        // Take only the LAST message (most recent/complete response)
                        const latestMsg = botMsgs[botMsgs.length - 1]
                        updateMessages([latestMsg])
                        setIsCopilotLoading(false)
                    } else if (!pollingComplete) {
                        setTimeout(poll, 5000)
                    }
                } catch (e) {
                    console.error("Summary poll error", e)
                    setIsCopilotLoading(false)
                }
            }

            poll()
        } catch (error) {
            console.error("Error generating summary:", error)
            setIsCopilotLoading(false)
        }
    }

    return {
        copilotMessages,
        chatHistory,
        isCopilotLoading,
        isSending,
        userMessage,
        setUserMessage,
        sendUserMessage,
        generateExecutiveSummary,
        resetChat
    }
}
