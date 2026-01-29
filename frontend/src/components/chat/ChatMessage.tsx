import React from 'react'
import Image from 'next/image'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import * as XLSX from 'xlsx'

// Helper to extract table data from Markdown node
const extractTableData = (node: any) => {
    try {
        // node -> thead -> tr -> th[]
        const headerRow = node.children[0]?.children?.[0]
        if (!headerRow) return null

        const headers = headerRow.children.map((th: any) => {
            // th -> textNode (sometimes text is nested specifically in ReactMarkdown AST)
            // safer to grab value from first child's val
            return th.children?.[0]?.value || ''
        })

        const rows = node.children[1]?.children.map((tr: any) =>
            tr.children.map((td: any) => td.children?.[0]?.value || '')
        )
        return { headers, rows }
    } catch (e) {
        console.error("Error extracting table data", e)
        return null
    }
}

// Markdown components configuration for Strategic Control Tower theme
const MarkdownComponents: any = {
    p: ({ node, ...props }: any) => <p className="mb-3 last:mb-0 leading-relaxed" {...props} />,
    h1: ({ node, ...props }: any) => <h1 className="text-xl font-bold mb-4 mt-5 text-[#102a43]" {...props} />,
    h2: ({ node, ...props }: any) => <h2 className="text-lg font-bold mb-3 mt-5 text-[#102a43]" {...props} />,
    h3: ({ node, ...props }: any) => <h3 className="font-semibold mb-2 mt-4 text-[#243b53]" {...props} />,
    ul: ({ node, ...props }: any) => <ul className="list-disc pl-5 mb-4 space-y-1.5" {...props} />,
    ol: ({ node, ...props }: any) => <ol className="list-decimal pl-5 mb-4 space-y-1.5" {...props} />,
    li: ({ node, ...props }: any) => <li className="text-[#486581]" {...props} />,
    blockquote: ({ node, ...props }: any) => (
        <blockquote className="border-l-3 border-[#14919b] pl-4 py-2 italic text-[#486581] my-4 bg-[#F5F7FA] rounded-r-lg" {...props} />
    ),
    code: ({ node, inline, className, children, ...props }: any) => {
        return inline ? (
            <code className="bg-[#EDF2F7] rounded px-1.5 py-0.5 font-mono text-sm text-[#14919b]" {...props}>{children}</code>
        ) : (
            <div className="rounded-xl overflow-hidden my-4 bg-[#102a43] shadow-lg">
                <pre className="p-4 overflow-x-auto text-[#9fb3c8] font-mono text-xs leading-relaxed">
                    <code {...props}>{children}</code>
                </pre>
            </div>
        )
    },
    table: ({ node, ...props }: any) => {
        const data = extractTableData(node)
        const isTaxonomyTable = data && data.headers.some((h: string) => {
            const lower = h.toLowerCase()
            return lower.includes('n4') || lower.includes('categoria') || lower.includes('hierarquia') || lower.includes('grupo')
        })

        const handleDownload = () => {
            if (!data) return

            // Format for Excel
            const wsData = [
                data.headers,
                ...data.rows
            ]

            // If it's a taxonomy table, try to split hierarchy if needed
            // But raw dump is fine for now as user can edit

            const ws = XLSX.utils.aoa_to_sheet(wsData)
            const wb = XLSX.utils.book_new()
            XLSX.utils.book_append_sheet(wb, ws, "Taxonomy")
            XLSX.writeFile(wb, "Sugestao_Taxonomia.xlsx")
        }

        return (
            <div className="my-5 rounded-xl border border-gray-200 shadow-sm overflow-hidden bg-white">
                {isTaxonomyTable && (
                    <div className="bg-gray-50 border-b border-gray-100 px-4 py-2 flex justify-between items-center">
                        <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Tabela de Sugestões</span>
                        <button
                            onClick={handleDownload}
                            className="text-xs flex items-center gap-1 text-[#38bec9] font-medium hover:text-[#2c9ca6] transition-colors"
                        >
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                            </svg>
                            Baixar Excel
                        </button>
                    </div>
                )}
                <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200" {...props} />
                </div>
            </div>
        )
    },
    thead: ({ node, ...props }: any) => <thead className="bg-[#F5F7FA]" {...props} />,
    th: ({ node, ...props }: any) => (
        <th className="px-4 py-3 text-left text-xs font-semibold text-[#486581] uppercase tracking-wider whitespace-nowrap" {...props} />
    ),
    td: ({ node, ...props }: any) => (
        <td className="px-4 py-3 text-sm text-[#486581] border-t border-gray-100 whitespace-pre-wrap" {...props} />
    ),
    tr: ({ node, ...props }: any) => <tr className="hover:bg-[#F5F7FA]/50 transition-colors" {...props} />,
    a: ({ node, ...props }: any) => (
        <a className="text-[#14919b] hover:text-[#0e7c86] hover:underline font-medium transition-colors" target="_blank" rel="noopener noreferrer" {...props} />
    ),
    strong: ({ node, ...props }: any) => <strong className="font-semibold text-[#102a43]" {...props} />,
    hr: ({ node, ...props }: any) => <hr className="my-6 border-gray-200" {...props} />,
}

export interface Message {
    from: 'user' | 'bot'
    text: string
    timestamp: Date
}

interface ChatMessageProps {
    message: Message
}

export default function ChatMessage({ message }: ChatMessageProps) {
    const isUser = message.from === 'user'

    return (
        <div className={`flex gap-4 animate-fadeIn ${isUser ? 'flex-row-reverse' : ''}`}>
            {/* Avatar */}
            {!isUser && (
                <div className="w-10 h-10 rounded-xl bg-white shadow-md flex items-center justify-center flex-shrink-0 overflow-hidden border border-gray-100">
                    <img
                        src="/agent-icon.png"
                        alt="AI Agent"
                        className="w-full h-full object-cover"
                    />
                </div>
            )}
            {isUser && (
                <div className="w-10 h-10 rounded-xl bg-[#102a43] flex items-center justify-center flex-shrink-0 shadow-md">
                    <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                    </svg>
                </div>
            )}

            {/* Message Content */}
            <div className={`flex-1 max-w-[85%] ${isUser ? 'text-right' : ''}`}>
                <div className={`inline-block rounded-2xl px-5 py-4 shadow-sm ${isUser
                    ? 'bg-[#102a43] text-white rounded-tr-md'
                    : 'bg-white text-[#486581] rounded-tl-md border border-[#102a43]/8'
                    }`}>
                    {isUser ? (
                        <p className="text-sm leading-relaxed">{message.text}</p>
                    ) : (
                        <div className="text-sm">
                            <ReactMarkdown remarkPlugins={[remarkGfm]} components={MarkdownComponents}>
                                {message.text}
                            </ReactMarkdown>


                        </div>
                    )}
                </div>
                <p className={`text-xs text-[#829ab1] mt-2 ${isUser ? 'text-right pr-1' : 'pl-1'}`}>
                    {message.timestamp instanceof Date && !isNaN(message.timestamp.getTime())
                        ? message.timestamp.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
                        : ''}
                </p>
            </div>
        </div>
    )
}

// Loading indicator component - Thinking animation
export function ChatMessageLoading() {
    return (
        <div className="flex gap-4 animate-fadeIn">
            <div className="w-10 h-10 rounded-xl bg-white shadow-md flex items-center justify-center flex-shrink-0 overflow-hidden border border-gray-100">
                <Image
                    src="/agent-icon.png"
                    alt="AI Agent"
                    width={40}
                    height={40}
                    className="w-full h-full object-cover"
                />
            </div>
            <div className="flex-1">
                <div className="inline-block bg-white rounded-2xl rounded-tl-md px-5 py-4 shadow-sm border border-gray-100">
                    <div className="flex items-center gap-3">
                        {/* Thinking dots */}
                        <div className="flex gap-1.5">
                            <div className="w-2 h-2 bg-[#14919b] rounded-full animate-thinking"></div>
                            <div className="w-2 h-2 bg-[#14919b] rounded-full animate-thinking delay-200"></div>
                            <div className="w-2 h-2 bg-[#14919b] rounded-full animate-thinking delay-300"></div>
                        </div>
                        <span className="text-sm text-[#829ab1]">Analisando dados...</span>
                    </div>
                </div>
            </div>
        </div>
    )
}
