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

// Helper to parse all markdown tables from raw text
const parseAllTables = (text: string) => {
    try {
        const lines = text.split('\n')
        const tables: any[] = []
        let currentTable: { headers: string[], rows: string[][] } | null = null

        for (let i = 0; i < lines.length; i++) {
            const line = lines[i].trim()
            if (line.startsWith('|')) {
                const parts = line.split('|').map(p => p.trim()).filter(p => p !== '')
                // Check if it's a separator line (e.g. |---|---|)
                const isSeparator = parts.every(p => p.match(/^[-:]+$/))

                if (!isSeparator) {
                    if (!currentTable) {
                        // Assume first row is header
                        currentTable = { headers: parts, rows: [] }
                        tables.push(currentTable)
                    } else {
                        // Add to current table rows
                        currentTable.rows.push(parts)
                    }
                }
            } else if (line === '' && currentTable) {
                // Empty line breaks table context
                currentTable = null
            }
        }
        return tables
    } catch (e) {
        console.error("Error parsing tables", e)
        return []
    }
}

export default function ChatMessage({ message }: ChatMessageProps) {
    const isUser = message.from === 'user'

    // Check for tables in the full text
    const hasTaxonomyTables = !isUser && (
        message.text.includes('|') &&
        (
            message.text.toLowerCase().includes('n4') ||
            message.text.toLowerCase().includes('categoria') ||
            message.text.toLowerCase().includes('unspsc') ||
            message.text.toLowerCase().includes('segment') // Covers Segmento/Segment
        )
    )

    const handleDownloadAll = () => {
        const tables = parseAllTables(message.text)
        if (tables.length === 0) return

        // Output Layout: N1, N2, N3, N4 only (no Grupo column)
        const newHeaders = ['N1', 'N2', 'N3', 'N4']
        const newRows: string[][] = []

        tables.forEach(t => {
            const headersLower = t.headers.map((h: string) => (h || '').toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, ""))

            // UNIVERSAL COLUMN DETECTION
            // 1. Find Grupo column
            let idxGrupo = headersLower.findIndex((h: string) => h.includes('grupo'))
            if (idxGrupo === -1) idxGrupo = 0 // Fallback to first column

            // 2. Find Hierarchy column (contains '>' in header name OR has '>' in first data row)
            let idxHierarchy = headersLower.findIndex((h: string) => h.includes('>') || h.includes('hierarquia'))
            if (idxHierarchy === -1 && t.rows.length > 0) {
                // Check first row for a cell containing '>'
                idxHierarchy = t.rows[0].findIndex((cell: string) => cell && cell.includes('>'))
            }

            // 3. Find N4/Categoria column
            let idxN4Source = headersLower.findIndex((h: string) =>
                h.includes('n4') || h.includes('categoria') || h.includes('sugestao')
            )

            t.rows.forEach((row: string[]) => {
                const grupo = row[idxGrupo] || ''
                const hierarchyRaw = idxHierarchy !== -1 ? (row[idxHierarchy] || '') : ''
                const n4Source = idxN4Source !== -1 ? (row[idxN4Source] || '') : ''

                let n1 = '', n2 = '', n3 = '', n4 = '', obs = ''

                // Check if it's a warning/observation - SKIP these rows (incomplete)
                if (hierarchyRaw.includes('⚠️') || hierarchyRaw.toLowerCase().includes('misturado')) {
                    // Skip - incomplete/mixed groups
                    return
                } else if (hierarchyRaw.includes('>')) {
                    // Split the hierarchy string
                    const parts = hierarchyRaw.split('>').map(p => p.trim()).filter(p => p.length > 0)

                    if (parts.length >= 1) n1 = parts[0]
                    if (parts.length >= 2) n2 = parts[1]
                    if (parts.length >= 3) n3 = parts[2]
                    if (parts.length >= 4) n4 = parts[3]
                    // If more than 4 parts, use the last one as N4
                    if (parts.length > 4) n4 = parts[parts.length - 1]
                } else {
                    // No hierarchy separator found - SKIP (incomplete)
                    return
                }

                // FILTER: Only include rows with COMPLETE taxonomy (N1, N2, N3, N4 all filled)
                if (n1 && n2 && n3 && n4) {
                    newRows.push([n1, n2, n3, n4])
                }
            })
        })

        // Sort rows by N1 > N2 > N3 > N4
        newRows.sort((a, b) => {
            const n1Comp = (a[0] || '').localeCompare(b[0] || '')
            if (n1Comp !== 0) return n1Comp
            const n2Comp = (a[1] || '').localeCompare(b[1] || '')
            if (n2Comp !== 0) return n2Comp
            const n3Comp = (a[2] || '').localeCompare(b[2] || '')
            if (n3Comp !== 0) return n3Comp
            return (a[3] || '').localeCompare(b[3] || '')
        })

        const ws = XLSX.utils.aoa_to_sheet([newHeaders, ...newRows])
        const wb = XLSX.utils.book_new()
        XLSX.utils.book_append_sheet(wb, ws, "Taxonomia_Consolidada")

        // Add Raw Data Sheet (Safety net)
        let rawHeader: string[] = []
        let rawRows: string[][] = []
        tables.forEach(t => {
            if (rawHeader.length === 0) rawHeader = t.headers
            rawRows = [...rawRows, ...t.rows]
        })
        const wsRaw = XLSX.utils.aoa_to_sheet([rawHeader, ...rawRows])
        XLSX.utils.book_append_sheet(wb, wsRaw, "Dados_Brutos")

        XLSX.writeFile(wb, "Taxonomia_N1_N4.xlsx")
    }

    return (
        <div className={`flex gap-4 animate-fadeIn ${isUser ? 'flex-row-reverse' : ''}`}>
            {/* Avatar */}
            {!isUser && (
                <div className="w-10 h-10 rounded-xl bg-white shadow-md flex items-center justify-center flex-shrink-0 overflow-hidden border border-gray-100">
                    <Image
                        src="/agent-icon.png"
                        alt="AI Agent"
                        width={40}
                        height={40}
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

                            {hasTaxonomyTables && (
                                <div className="mt-4 pt-4 border-t border-gray-100 flex justify-start">
                                    <button
                                        onClick={handleDownloadAll}
                                        className="flex items-center gap-2 px-3 py-1.5 bg-[#14919b]/10 text-[#14919b] text-sm font-medium rounded-lg hover:bg-[#14919b]/20 transition-colors"
                                    >
                                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                                        </svg>
                                        Baixar Excel Consolidado (Todos os Lotes)
                                    </button>
                                </div>
                            )}
                        </div>
                    )}
                </div>
                <p className={`text-xs text-[#829ab1] mt-2 ${isUser ? 'text-right pr-1' : 'pl-1'}`}>
                    {message.timestamp.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}
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
