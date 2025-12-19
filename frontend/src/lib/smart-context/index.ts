/**
 * @fileoverview Smart Context - Local RAG (Retrieval-Augmented Generation) System.
 * 
 * This module provides the main exports for the Smart Context system:
 * - generateSmartContext: Processes user queries and generates context payloads
 * - formatSmartContextMessage: Formats the final message for Copilot
 * 
 * The Smart Context system enriches user queries with relevant data from
 * the classification results before sending to the Copilot, enabling
 * data-aware responses without requiring the LLM to have direct data access.
 * 
 * @module smart-context
 * 
 * @example
 * ```typescript
 * const context = generateSmartContext("Top 10 categorias N2", items);
 * if (context) {
 *   const message = formatSmartContextMessage(query, context);
 *   // Send message to Copilot
 * }
 * ```
 */

import { extractEntities } from './entity-extractor';
import { routeIntent } from './intent-router';
import { executeIntent } from './execution-engine';
import { ContextPayload, SmartContextQuery, IntentType } from './types';

/**
 * Main entry point for generating Smart Context from a user query.
 * 
 * Processes the query through three stages:
 * 1. Entity Extraction: Identifies categories, numbers, terms, etc.
 * 2. Intent Routing: Determines the type of question being asked
 * 3. Intent Execution: Generates the data payload for the detected intent
 * 
 * @param query - The user's natural language question
 * @param items - Array of classified items from the active session
 * @returns ContextPayload with data and instructions, or null if no context found
 */
export const generateSmartContext = (query: string, items: any[]): ContextPayload | null => {
    // 1. Extract Entities (Who/What)
    const entities = extractEntities(query, items);

    // 2. Decode Intent (Why/How)
    let intent = routeIntent(query);

    // Intent Refinement based on Entity Presence
    if (intent === IntentType.UNKNOWN) {
        if (entities.category) {
            intent = IntentType.CATEGORY_LOOKUP;
        }
    }

    // 3. Execute and return payload
    return executeIntent(intent, entities, items);
}

/**
 * Formats a Smart Context payload into a complete Copilot message.
 * 
 * Creates a structured prompt with:
 * - Role instruction (act as data analyst)
 * - Mandatory instructions for the AI
 * - JSON data block with the context
 * - Original user question
 * 
 * @param query - The original user question
 * @param payload - The generated context payload
 * @returns Formatted prompt string ready to send to Copilot
 */
export const formatSmartContextMessage = (query: string, payload: ContextPayload): string => {
    return `
ATUE COMO UM ANALISTA DE DADOS SÊNIOR.
Sua tarefa é analisar os dados JSON fornecidos abaixo e responder à pergunta do usuário.

INSTRUÇÕES OBRIGATÓRIAS:
1. Analise os dados fornecidos nesta mensagem. NÃO peça mais informações.
2. Use APENAS os dados fornecidos no bloco JSON.
3. Responda em Português do Brasil de forma clara e direta.
4. ${payload.instructions}

DADOS DA ANÁLISE(JSON):
\`\`\`json
${JSON.stringify(payload.data, null, 2)}
\`\`\`

PERGUNTA DO USUÁRIO:
"${query}"
`.trim();
}

export * from './types';

