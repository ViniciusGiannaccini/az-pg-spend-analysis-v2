import { useState, useCallback } from 'react'
import { apiClient } from '@/lib/api'
import * as XLSX from 'xlsx'

interface ValidationCheck {
    label: string
    status: 'ok' | 'warning' | 'error'
    message: string
}

interface ValidationStatus {
    isValid: boolean
    score: number
    checks: ValidationCheck[]
}

interface UseModelTrainingReturn {
    // State
    trainingStep: 'upload' | 'preview' | 'training' | 'result'
    trainingFile: { file: File; content: string } | null
    previewData: any[]
    validationStatus: ValidationStatus | null
    trainingResult: any | null
    modelHistory: any[]

    // Actions
    handleTrainingFileSelect: (file: File, fileContent: string) => void
    confirmTraining: (sector: string) => Promise<void>
    cancelTraining: () => void
    loadModelHistory: (sector: string) => Promise<void>
    handleRestoreModel: (sector: string, versionId: string) => Promise<void>
}

export function useModelTraining(): UseModelTrainingReturn {
    const [trainingStep, setTrainingStep] = useState<'upload' | 'preview' | 'training' | 'result'>('upload')
    const [trainingFile, setTrainingFile] = useState<{ file: File; content: string } | null>(null)
    const [previewData, setPreviewData] = useState<any[]>([])
    const [validationStatus, setValidationStatus] = useState<ValidationStatus | null>(null)
    const [trainingResult, setTrainingResult] = useState<any | null>(null)
    const [modelHistory, setModelHistory] = useState<any[]>([])

    const normalizeHeader = (header: string): string => {
        const normalized = header.toString().toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim()

        if (['descricao', 'item_description', 'description', 'desc'].includes(normalized)) return 'Descrição'
        if (['n1', 'nivel 1', 'level 1'].includes(normalized)) return 'N1'
        if (['n2', 'nivel 2', 'level 2'].includes(normalized)) return 'N2'
        if (['n3', 'nivel 3', 'level 3'].includes(normalized)) return 'N3'
        if (['n4', 'nivel 4', 'level 4', 'subcategoria'].includes(normalized)) return 'N4'

        return header
    }

    const validateTrainingData = (data: any[]) => {
        const checks: ValidationCheck[] = []
        let validRows = 0
        let score = 100

        if (data.length === 0) {
            setValidationStatus({ isValid: false, score: 0, checks: [{ label: "Dados", status: 'error', message: "Arquivo vazio." }] })
            return
        }

        const headers = Object.keys(data[0])
        const requiredCols = ["Descrição", "N1", "N2", "N3", "N4"]

        const headerMap: Record<string, string> = {}
        headers.forEach(h => {
            headerMap[normalizeHeader(h)] = h
        })

        const missingCols = requiredCols.filter(req => !headerMap[req])

        if (missingCols.length === 0) {
            checks.push({ label: "Estrutura do Arquivo", status: 'ok', message: "Colunas identificadas corretamente." })
        } else {
            checks.push({
                label: "Estrutura do Arquivo",
                status: 'error',
                message: `Faltando colunas: ${missingCols.join(", ")}. Aceitamos variações (ex: Descricao, DESCRICAO).`
            })
            score = 0
        }

        if (missingCols.length === 0) {
            let emptyRows = 0

            const descKey = headerMap["Descrição"]
            const n1Key = headerMap["N1"]
            const n2Key = headerMap["N2"]
            const n3Key = headerMap["N3"]
            const n4Key = headerMap["N4"]

            data.forEach(row => {
                const desc = row[descKey]
                const n1 = row[n1Key]
                const n2 = row[n2Key]
                const n3 = row[n3Key]
                const n4 = row[n4Key]

                const isRowEmpty =
                    !desc || desc.toString().trim() === "" ||
                    !n1 || n1.toString().trim() === "" ||
                    !n2 || n2.toString().trim() === "" ||
                    !n3 || n3.toString().trim() === "" ||
                    !n4 || n4.toString().trim() === "" ||
                    n4.toString().toLowerCase() === "nenhum" ||
                    n4.toString().toLowerCase() === "ambíguo"

                if (isRowEmpty) {
                    emptyRows++
                } else {
                    validRows++
                }
            })

            const total = data.length
            score = Math.floor((validRows / total) * 100)

            if (emptyRows > 0) {
                checks.push({
                    label: "Completude dos Dados",
                    status: 'error',
                    message: `${emptyRows} linhas incompletas (Campos vazios ou 'Nenhum'/'Ambíguo'). Todas as colunas devem estar 100% preenchidas.`
                })
                if (score === 100) score = 99
            } else {
                checks.push({ label: "Completude dos Dados", status: 'ok', message: "Todas as linhas estão completas." })
            }

            if (validRows < 10) {
                checks.push({ label: "Volume de Dados", status: 'error', message: `Poucos dados válidos (${validRows}). Mínimo de 10 exemplos necessários.` })
            } else {
                checks.push({ label: "Volume de Dados", status: 'ok', message: `${validRows} exemplos válidos para treino.` })
            }
        }

        const passedErrors = !checks.some(c => c.status === 'error')

        setValidationStatus({
            isValid: passedErrors,
            score: Math.max(0, score),
            checks
        })
    }

    const handleTrainingFileSelect = async (file: File, fileContent: string) => {
        setTrainingFile({ file, content: fileContent })
        setTrainingStep('preview')

        try {
            const byteCharacters = atob(fileContent)
            const byteNumbers = new Array(byteCharacters.length)
            for (let i = 0; i < byteCharacters.length; i++) {
                byteNumbers[i] = byteCharacters.charCodeAt(i)
            }
            const byteArray = new Uint8Array(byteNumbers)
            const workbook = XLSX.read(byteArray, { type: 'array' })
            const firstSheet = workbook.Sheets[workbook.SheetNames[0]]
            const jsonData = XLSX.utils.sheet_to_json(firstSheet)

            validateTrainingData(jsonData)
            setPreviewData(jsonData.slice(0, 10))

        } catch (error) {
            console.error("Error parsing validation file:", error)
            setValidationStatus({
                isValid: false,
                score: 0,
                checks: [{ label: "Leitura do Arquivo", status: 'error', message: "Erro ao ler arquivo Excel." }]
            })
        }
    }

    const confirmTraining = async (sector: string) => {
        if (!trainingFile) return

        setTrainingStep('training')
        setTrainingResult(null)

        try {
            const result = await apiClient.trainModel(trainingFile.content, sector, trainingFile.file.name)
            setTrainingResult(result)
            setTrainingStep('result')
        } catch (error) {
            console.error('Error training model:', error)
            setTrainingStep('preview')
            alert('Erro ao treinar modelo. Tente novamente.')
        }
    }

    const cancelTraining = useCallback(() => {
        setTrainingStep('upload')
        setTrainingFile(null)
        setPreviewData([])
        setValidationStatus(null)
    }, [])

    const loadModelHistory = async (sector: string) => {
        try {
            const history = await apiClient.getModelHistory(sector)
            setModelHistory(history)
        } catch (error) {
            console.error("Failed to load model history", error)
        }
    }

    const handleRestoreModel = async (sector: string, versionId: string) => {
        if (!confirm("Tem certeza que deseja restaurar esta versão do modelo?")) return

        try {
            await apiClient.setActiveModel(sector, versionId)
            alert("Modelo restaurado com sucesso!")
            loadModelHistory(sector)
        } catch (error) {
            console.error("Error restoring model:", error)
            alert("Erro ao restaurar modelo.")
        }
    }

    return {
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
    }
}
