
export enum IntentType {
    COUNT_FILTERED = 'COUNT_FILTERED',
    TOP_N_RANKING = 'TOP_N_RANKING',
    BOTTOM_N_RANKING = 'BOTTOM_N_RANKING',
    DISTRIBUTION = 'DISTRIBUTION',
    TERM_SEARCH = 'TERM_SEARCH',
    TERM_EXCEPTION = 'TERM_EXCEPTION',
    HIERARCHY_LOOKUP = 'HIERARCHY_LOOKUP',
    CATEGORY_LOOKUP = 'CATEGORY_LOOKUP',
    GAP_ANALYSIS = 'GAP_ANALYSIS',
    OUTLIER_DETECTION = 'OUTLIER_DETECTION',
    PARETO_ANALYSIS = 'PARETO_ANALYSIS',
    UNKNOWN = 'UNKNOWN'
}

export interface SmartContextQuery {
    intent: IntentType;
    entities: {
        category?: string; // e.g. "Indiretos"
        level?: 'N1' | 'N2' | 'N3' | 'N4';
        targetLevel?: 'N1' | 'N2' | 'N3' | 'N4'; // For "subcategories of X"
        targetType?: 'item' | 'category' | 'word';
        number?: number; // e.g. 5, 10
        term?: string; // e.g. "Parafuso"
        threshold?: number; // e.g. length < 5
        status?: 'unique' | 'ambiguous' | 'unclassified' | 'all';
    };
    originalQuery: string;
}


export interface ContextPayload {
    data: any; // Raw JSON data of the context
    text: string; // Formatted text representation for the prompt
    instructions: string; // Specific instructions for this context type
    relevantItems: any[]; // Subset of items for further inspection if needed
    meta?: any; // Structured data for potential UI widgets
}
