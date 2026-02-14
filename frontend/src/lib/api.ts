/**
 * @fileoverview HTTP API client for Spend Analysis application.
 * 
 * This module provides the centralized API client for all HTTP communications:
 * - Azure Function endpoints (classification, training, model management)
 * - Microsoft Direct Line API (Copilot chat communication)
 * 
 * @module api
 */

import axios, { AxiosRequestConfig } from 'axios'

/** Base URL for the Azure Functions API (configurable via environment) */
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:7071/api'

/** Function key for Azure Functions authentication (optional, for production) */
const FUNCTION_KEY = process.env.NEXT_PUBLIC_FUNCTION_KEY || ''

/**
 * Generates authentication headers for Azure Functions requests.
 * Only includes the x-functions-key header when a key is configured.
 * @returns Record containing auth headers, or empty object
 */
const getAuthHeaders = (): Record<string, string> => {
    if (FUNCTION_KEY) {
        return { 'x-functions-key': FUNCTION_KEY }
    }
    return {}
}

/**
 * Response from the Direct Line token endpoint.
 */
export interface DirectLineToken {
    /** Unique conversation identifier */
    conversationId: string
    /** Bearer token for Direct Line API authentication */
    token: string
    /** Token expiration time in seconds */
    expires_in: number
}

/**
 * Represents a classification session (deprecated - use TaxonomySession from hooks).
 * @deprecated Use TaxonomySession from useTaxonomySession hook instead
 */
export interface ClassificationSession {
    sessionId: string
    filename: string
    sector: string
    fileContent: string
    summary?: any
    analytics?: any
}

/**
 * Centralized API client containing all HTTP methods for the application.
 * 
 * @example
 * ```typescript
 * // Classification
 * const result = await apiClient.processTaxonomy(fileContent, dictContent, 'Varejo', 'file.xlsx')
 * 
 * // Chat
 * const token = await apiClient.getDirectLineToken()
 * await apiClient.sendMessageToCopilot(token.conversationId, token.token, 'Hello')
 * ```
 */
export const apiClient = {
    /**
     * Gets a temporary Direct Line token for Copilot chat communication.
     * The token is valid for 30 minutes and should not be cached long-term.
     * @returns Promise resolving to DirectLineToken with conversationId and token
     */
    async getDirectLineToken(): Promise<DirectLineToken> {
        const response = await axios.get(`${API_BASE_URL}/get-token`, {
            headers: getAuthHeaders()
        })
        return response.data
    },

    // Process Excel file for taxonomy classification (Async Polling)
    async processTaxonomy(
        fileContent: string,
        dictionaryContent: string,
        sector: string,
        originalFilename: string,
        customHierarchy?: string, // Optional custom hierarchy base64
        clientContext?: string,   // Optional client context
        onProgress?: (msg: string, pct: number) => void // Callback for progress updates
    ): Promise<any> {
        const requestBody: any = {
            fileContent,
            dictionaryContent,
            sector,
            originalFilename,
            clientContext: clientContext || ""
        }

        // Only include customHierarchy if provided
        if (customHierarchy) {
            requestBody.customHierarchy = customHierarchy
        }

        console.log("[API] Submitting Taxonomy Job...");

        // 1. Submit Job
        const submitResponse = await axios.post(`${API_BASE_URL}/SubmitTaxonomyJob`, requestBody, {
            headers: getAuthHeaders()
        });

        const jobId = submitResponse.data.jobId;
        console.log(`[API] Job submitted. ID: ${jobId}`);

        if (onProgress) onProgress("Upload concluído. Aguardando início...", 0);

        // 2. Poll for Completion
        const maxRetries = 600; // 50 minutes max (5s interval)
        let attempts = 0;

        while (attempts < maxRetries) {
            await new Promise(resolve => setTimeout(resolve, 5000)); // Wait 5s

            try {
                const statusRes = await axios.get(`${API_BASE_URL}/GetTaxonomyJobStatus`, {
                    params: { jobId },
                    headers: getAuthHeaders()
                });

                const status = statusRes.data;
                console.log(`[API] Job Status: ${status.status} (${status.progress_pct}%)`);

                if (onProgress) {
                    onProgress(status.message || "Processando...", status.progress_pct || 0);
                }

                if (status.status === 'COMPLETED') {
                    // The result is the response body itself in the new design (or loaded from it)
                    // Our backend returns the full JSON when completed.
                    return { ...status, sessionId: status.jobId || status.sessionId };
                }

                if (status.status === 'ERROR') {
                    throw new Error(status.message || "Erro desconhecido no processamento");
                }

            } catch (e: any) {
                // Stop polling on 404 (job not found) - don't retry forever
                if (e?.response?.status === 404) {
                    throw new Error("Job não encontrado no servidor. Por favor, tente novamente.");
                }
                console.warn("[API] Polling error (retrying):", e);
            }

            attempts++;
        }

        throw new Error("Timeout aguardando processamento do arquivo.");
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
        console.log(`[API] Fetching model history for sector: ${sector} from ${API_BASE_URL}/GetModelHistory`)
        try {
            const response = await axios.get(`${API_BASE_URL}/GetModelHistory`, {
                params: { sector, t: Date.now() },
                headers: getAuthHeaders()
            })
            console.log(`[API] Model history received: ${response.data?.length} entries`)
            return response.data
        } catch (error) {
            console.error('[API] Error fetching model history:', error)
            throw error
        }
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
