
import { extractEntities } from './entity-extractor';
import { routeIntent } from './intent-router';
import { executeIntent } from './execution-engine';
import { ContextPayload, SmartContextQuery, IntentType } from './types';

export const generateSmartContext = (query: string, items: any[]): ContextPayload | null => {
    // 1. Extract Entities (Who/What)
    const entities = extractEntities(query, items);

    // 2. Decode Intent (Why/How)
    // We pass the query. We might improve routing if we know entities found.
    // e.g. "Software" -> if Category entity found, it heavily implies CATEGORY_LOOKUP if no other verb.
    let intent = routeIntent(query);

    // Intent Refinement based on Entity Presence
    if (intent === IntentType.UNKNOWN) {
        if (entities.category) {
            intent = IntentType.CATEGORY_LOOKUP;
        }
    }

    // 3. Execute

    // 3. Execute
    return executeIntent(intent, entities, items);
}


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
