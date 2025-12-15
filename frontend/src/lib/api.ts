import axios, { AxiosRequestConfig } from 'axios'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:7071/api'
const FUNCTION_KEY = process.env.NEXT_PUBLIC_FUNCTION_KEY || ''

// Helper to add Function Key header for Azure Functions (production only)
const getAuthHeaders = (): Record<string, string> => {
    if (FUNCTION_KEY) {
        return { 'x-functions-key': FUNCTION_KEY }
    }
    return {}
}

export interface DirectLineToken {
    conversationId: string
    token: string
    expires_in: number
}

export interface ClassificationSession {
    sessionId: string
    filename: string
    sector: string
    fileContent: string
    summary?: any
    analytics?: any
}

export const apiClient = {
    // Get Direct Line token for chat
    async getDirectLineToken(): Promise<DirectLineToken> {
        const response = await axios.get(`${API_BASE_URL}/get-token`, {
            headers: getAuthHeaders()
        })
        return response.data
    },

    // Process Excel file for taxonomy classification
    async processTaxonomy(
        fileContent: string,
        dictionaryContent: string,
        sector: string,
        originalFilename: string,
        customHierarchy?: string  // Optional custom hierarchy base64
    ): Promise<any> {
        const requestBody: any = {
            fileContent,
            dictionaryContent,
            sector,
            originalFilename
        }

        // Only include customHierarchy if provided
        if (customHierarchy) {
            requestBody.customHierarchy = customHierarchy
        }

        const response = await axios.post(`${API_BASE_URL}/ProcessTaxonomy`, requestBody, {
            headers: getAuthHeaders()
        })
        return response.data
    },

    // Generic method to post any activity to Direct Line
    async postActivity(conversationId: string, token: string, activity: any): Promise<any> {
        console.log('[DIRECT LINE ACTIVITY]', JSON.stringify(activity, null, 2));
        const response = await axios.post(
            `https://directline.botframework.com/v3/directline/conversations/${conversationId}/activities`,
            activity,
            {
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            }
        )
        return response.data
    },

    // Send message to Copilot Studio via Direct Line
    async sendMessageToCopilot(conversationId: string, token: string, text: string, value?: any): Promise<void> {
        const payload = {
            type: 'message',
            from: { id: 'user' },
            locale: 'pt-BR',
            text: text,
            value: value
        };

        console.log('[DIRECT LINE PAYLOAD]', JSON.stringify(payload, null, 2));

        await axios.post(
            `https://directline.botframework.com/v3/directline/conversations/${conversationId}/activities`,
            payload,
            {
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            }
        )
    },

    // Get messages from Copilot Studio via Direct Line
    async getMessagesFromCopilot(conversationId: string, token: string, watermark?: string): Promise<any> {
        const url = watermark
            ? `https://directline.botframework.com/v3/directline/conversations/${conversationId}/activities?watermark=${watermark}`
            : `https://directline.botframework.com/v3/directline/conversations/${conversationId}/activities`

        const response = await axios.get(url, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        })
        return response.data
    },

    // Train ML Model
    async trainModel(
        fileContent: string,
        sector: string,
        filename: string
    ): Promise<any> {
        const response = await axios.post(`${API_BASE_URL}/TrainModel`, {
            fileContent,
            sector,
            filename
        }, {
            headers: getAuthHeaders()
        })
        return response.data
    },

    async getModelHistory(sector: string): Promise<any[]> {
        const response = await axios.get(`${API_BASE_URL}/GetModelHistory`, {
            params: { sector, t: Date.now() },
            headers: getAuthHeaders()
        })
        return response.data
    },

    async setActiveModel(sector: string, versionId: string): Promise<any> {
        const response = await axios.post(`${API_BASE_URL}/SetActiveModel`, {
            sector,
            version_id: versionId
        }, {
            headers: getAuthHeaders()
        })
        return response.data
    },

    async getModelInfo(sector: string, versionId?: string): Promise<any> {
        const response = await axios.get(`${API_BASE_URL}/GetModelInfo`, {
            params: { sector, version_id: versionId, t: Date.now() },
            headers: getAuthHeaders()
        })
        return response.data
    },

    async getTrainingData(
        sector: string,
        page: number = 1,
        pageSize: number = 50,
        filters?: { version?: string; n4?: string; search?: string }
    ): Promise<any> {
        const response = await axios.get(`${API_BASE_URL}/GetTrainingData`, {
            params: {
                sector,
                page,
                page_size: pageSize,
                ...filters
            },
            headers: getAuthHeaders()
        })
        return response.data
    },

    async deleteTrainingData(
        sector: string,
        options: { row_ids?: number[]; version?: string; items?: { descricao: string; n4: string; version: string }[] }
    ): Promise<any> {
        const response = await axios.post(`${API_BASE_URL}/DeleteTrainingData`, {
            sector,
            ...options
        }, {
            headers: getAuthHeaders()
        })
        return response.data
    }
}
