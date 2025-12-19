/**
 * @fileoverview Intent Router for Smart Context queries.
 * 
 * This module identifies the user's intention from their natural language query
 * by matching against predefined regex patterns. Each intent type corresponds
 * to a specific data operation in the execution engine.
 * 
 * @module smart-context/intent-router
 */

import { IntentType } from './types'
import { normalize } from './entity-extractor'

/**
 * Maps a regex pattern to an intent type.
 */
interface IntentPattern {
    /** The intent type to return when the pattern matches */
    type: IntentType;
    /** Regex pattern to match against normalized query */
    regex: RegExp;
}

/**
 * Ordered list of intent patterns for query classification.
 * Patterns are checked in order; first match wins.
 * More specific patterns should come before general ones.
 */
const INTENT_PATTERNS: IntentPattern[] = [
    // 1. OUTLIER_DETECTION - Detects short/vague descriptions
    { type: IntentType.OUTLIER_DETECTION, regex: /(?:menos de|curtas|vagas).*(?:caracteres|letras)/ },

    // 1.5 PARETO / CURVE A - 80/20 analysis
    { type: IntentType.PARETO_ANALYSIS, regex: /(?:pareto|curva a|80\/20|80-20|principais itens que representam)/ },

    // 2. GAP_ANALYSIS - Missing subcategories
    { type: IntentType.GAP_ANALYSIS, regex: /(?:sem subcategorias|nao possuem.*subcategoria)/ },

    // 3. TERM_EXCEPTION (Must be before simple search) - Items with term NOT in category
    { type: IntentType.TERM_EXCEPTION, regex: /(?:possui|contem|tem).*(?:termo|palavra).*(?:mas nao|fora de)/ },

    // 4. TERM_SEARCH - Items containing specific term
    { type: IntentType.TERM_SEARCH, regex: /(?:quais|que).*(?:contem|contém|possuem|tem).*(?:termo|palavra)/ },
    { type: IntentType.TERM_SEARCH, regex: /(?:onde|em que).*(?:termo|palavra).*(?:aparece)/ },
    { type: IntentType.TERM_SEARCH, regex: /(?:buscar por|procurar por)/ },

    // 5. TOP_N_RANKING - Top categories by count
    { type: IntentType.TOP_N_RANKING, regex: /(?:top|maiores|mais).*(?:quantidade|frequentes|itens|categorias|subcategorias|descricoes|termos|n[1-4])/ },
    { type: IntentType.TOP_N_RANKING, regex: /(?:variedade).*(?:descrições|unicas)/ },

    // 6. BOTTOM_N_RANKING - Least common categories
    { type: IntentType.BOTTOM_N_RANKING, regex: /(?:menor|menos).*(?:quantidade|itens)/ },
    { type: IntentType.BOTTOM_N_RANKING, regex: /(?:apenas 1|um unico|um único).*(?:item)/ },

    // 7. HIERARCHY_LOOKUP - Full category path
    { type: IntentType.HIERARCHY_LOOKUP, regex: /(?:hierarquia|caminho).*(?:completa)?/ },

    // 8. DISTRIBUTION - Percentage breakdown
    { type: IntentType.DISTRIBUTION, regex: /(?:distribuicao|distribuição|percentual|porcentagem)/ },
    { type: IntentType.DISTRIBUTION, regex: /(?:compoem|compõem).*(?:categoria pai)/ },

    // 9. COUNT_FILTERED - Simple count queries
    { type: IntentType.COUNT_FILTERED, regex: /(?:quantos|qual a contagem|numero de).*(?:itens|linhas|registros)/ },

    // 10. CATEGORY_LOOKUP (Sampling / General) - Show items from category
    { type: IntentType.CATEGORY_LOOKUP, regex: /(?:liste|exemplos|amostragem|aleatorios)/ },
    { type: IntentType.CATEGORY_LOOKUP, regex: /(?:fale sobre|analise|resumo)/ },
];

/**
 * Routes a user query to the appropriate intent type.
 * 
 * Normalizes the query text and checks it against all defined patterns
 * in order. Returns the first matching intent, or UNKNOWN if no match.
 * 
 * @param query - The user's natural language question
 * @returns The detected IntentType, or UNKNOWN if no pattern matches
 * 
 * @example
 * ```typescript
 * routeIntent("Top 10 categorias N2"); // Returns IntentType.TOP_N_RANKING
 * routeIntent("Hello world"); // Returns IntentType.UNKNOWN
 * ```
 */
export const routeIntent = (query: string): IntentType => {
    const qNorm = normalize(query);

    for (const pattern of INTENT_PATTERNS) {
        if (pattern.regex.test(qNorm)) {
            return pattern.type;
        }
    }

    // Fallback: If no specific intent matched, return UNKNOWN
    // The caller (index.ts) may upgrade this to CATEGORY_LOOKUP if a category entity was found
    return IntentType.UNKNOWN;
}

