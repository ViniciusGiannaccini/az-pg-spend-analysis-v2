
import { IntentType } from './types'
import { normalize } from './entity-extractor'

interface IntentPattern {
    type: IntentType;
    regex: RegExp;
}

const INTENT_PATTERNS: IntentPattern[] = [
    // 1. OUTLIER_DETECTION
    { type: IntentType.OUTLIER_DETECTION, regex: /(?:menos de|curtas|vagas).*(?:caracteres|letras)/ },

    // 1.5 PARETO / CURVE A
    { type: IntentType.PARETO_ANALYSIS, regex: /(?:pareto|curva a|80\/20|80-20|principais itens que representam)/ },

    // 2. GAP_ANALYSIS
    { type: IntentType.GAP_ANALYSIS, regex: /(?:sem subcategorias|nao possuem.*subcategoria)/ },

    // 3. TERM_EXCEPTION (Must be before simple search)
    { type: IntentType.TERM_EXCEPTION, regex: /(?:possui|contem|tem).*(?:termo|palavra).*(?:mas nao|fora de)/ },

    // 4. TERM_SEARCH
    { type: IntentType.TERM_SEARCH, regex: /(?:quais|que).*(?:contem|contém|possuem|tem).*(?:termo|palavra)/ },
    { type: IntentType.TERM_SEARCH, regex: /(?:onde|em que).*(?:termo|palavra).*(?:aparece)/ },
    { type: IntentType.TERM_SEARCH, regex: /(?:buscar por|procurar por)/ },

    // 5. TOP_N_RANKING
    { type: IntentType.TOP_N_RANKING, regex: /(?:top|maiores|mais).*(?:quantidade|frequentes|itens|categorias|subcategorias|descricoes|termos|n[1-4])/ },
    { type: IntentType.TOP_N_RANKING, regex: /(?:variedade).*(?:descrições|unicas)/ }, // "Maior variedade" usually is a top ranking of unique counts

    // 6. BOTTOM_N_RANKING
    { type: IntentType.BOTTOM_N_RANKING, regex: /(?:menor|menos).*(?:quantidade|itens)/ },
    { type: IntentType.BOTTOM_N_RANKING, regex: /(?:apenas 1|um unico|um único).*(?:item)/ }, // Special case for "1 item only"

    // 7. HIERARCHY_LOOKUP
    { type: IntentType.HIERARCHY_LOOKUP, regex: /(?:hierarquia|caminho).*(?:completa)?/ },

    // 8. DISTRIBUTION
    { type: IntentType.DISTRIBUTION, regex: /(?:distribuicao|distribuição|percentual|porcentagem)/ },
    { type: IntentType.DISTRIBUTION, regex: /(?:compoem|compõem).*(?:categoria pai)/ }, // Composition is distribution

    // 9. COUNT_FILTERED
    { type: IntentType.COUNT_FILTERED, regex: /(?:quantos|qual a contagem|numero de).*(?:itens|linhas|registros)/ },

    // 10. CATEGORY_LOOKUP (Sampling / General)
    { type: IntentType.CATEGORY_LOOKUP, regex: /(?:liste|exemplos|amostragem|aleatorios)/ },
    { type: IntentType.CATEGORY_LOOKUP, regex: /(?:fale sobre|analise|resumo)/ },
];

export const routeIntent = (query: string): IntentType => {
    const qNorm = normalize(query);

    for (const pattern of INTENT_PATTERNS) {
        if (pattern.regex.test(qNorm)) {
            return pattern.type;
        }
    }

    // Fallback: If no specific intent matched but we likely have a "Category Lookup" (implicit)
    // We defer to the caller to check if a Category Entity was found. If yes -> CATEGORY_LOOKUP.
    return IntentType.UNKNOWN;
}
