
// Levenshtein distance helper (Same as before, moved here)
export const levenshtein = (a: string, b: string): number => {
    if (!a || !b) return (a || b).length;
    const matrix = Array.from({ length: b.length + 1 }, (_, i) => [i])
        .concat(Array.from({ length: a.length + 1 }).map((_, i) => Array(b.length + 1).fill(0).map((__, j) => j === 0 ? i : 0))[0].slice(1) as any)

    for (let i = 1; i <= b.length; i++) matrix[i][0] = i
    for (let j = 1; j <= a.length; j++) matrix[0][j] = j

    for (let i = 1; i <= b.length; i++) {
        for (let j = 1; j <= a.length; j++) {
            if (b.charAt(i - 1) === a.charAt(j - 1)) {
                matrix[i][j] = matrix[i - 1][j - 1]
            } else {
                matrix[i][j] = Math.min(
                    matrix[i - 1][j - 1] + 1, // substitution
                    matrix[i][j - 1] + 1,     // insertion
                    matrix[i - 1][j] + 1      // deletion
                )
            }
        }
    }
    return matrix[b.length][a.length]
}

export const normalize = (s: string) => s.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase()

export interface EntityExtractionResult {
    category?: string;
    level?: 'N1' | 'N2' | 'N3' | 'N4';
    targetLevel?: 'N1' | 'N2' | 'N3' | 'N4';
    targetType?: 'item' | 'category' | 'word';
    number?: number;
    term?: string;
    threshold?: number;
    status?: 'unique' | 'ambiguous' | 'unclassified' | 'all'; // New field for classification status queries
}

export const extractEntities = (query: string, items: any[]): EntityExtractionResult => {
    const queryNorm = normalize(query);
    const result: EntityExtractionResult = {};

    // 1. Extract Numbers (Top N, Less than N)
    // Matches "Top 5", "5 exemplos", "menos de 3", "3 caracteres"
    const numberMatch = queryNorm.match(/(?:top|os|as|de)\s+(\d+)|(\d+)\s+(?:exemplos|itens|caracteres)/);
    if (numberMatch) {
        result.number = parseInt(numberMatch[1] || numberMatch[2], 10);
    }
    // Default number if TOP is asked but no number
    if (!result.number && queryNorm.includes('top')) {
        result.number = 5;
    }

    // 2. Extract Terms (Quoted or after 'termo')
    // Matches "termo [X]", "termo 'X'", "termo "X"", or just quoted "X"
    const termMatch = query.match(/termo\s+["']?([^"']+)["']?|["']([^"']+)["']/i);
    if (termMatch) {
        result.term = termMatch[1] || termMatch[2];
    }

    // 2.5 Identify Target Type (Item vs Category)
    // Helps decide if we should list Top Descriptions or Top Subcategories
    // Added 'top ... itens' specific check
    if (queryNorm.match(/(?:itens|produtos|materiais|descricoes|exemplos)/) || queryNorm.match(/top \d+ itens/)) {
        result.targetType = 'item';
    } else if (queryNorm.match(/(?:categorias|subcategorias|grupos|familias)/)) {
        result.targetType = 'category';
    } else if (queryNorm.match(/(?:palavras|termos|vocabulos)/)) {
        result.targetType = 'word';
    }

    // 2.6 Extract Classification Status (Unique, Ambiguous)
    if (queryNorm.match(/(?:unicos|univos|unica|unico|sucesso)/)) {
        result.status = 'unique';
    } else if (queryNorm.match(/(?:ambiguos|ambiguidade|duvida|revisar)/)) {
        result.status = 'ambiguous';
    } else if (queryNorm.match(/(?:nao classificado|sem classificacao|nenhum)/)) {
        result.status = 'unclassified';
    } else if (queryNorm.match(/(?:status|qualidade|metricas)/)) {
        result.status = 'all'; // General status breakdown
    }

    // 3. Extract Levels (N1, N2, Subcategoria)
    // Primary Level (what we are looking FOR)
    if (queryNorm.includes('nivel 1') || queryNorm.includes('n1')) result.level = 'N1';
    else if (queryNorm.includes('nivel 2') || queryNorm.includes('n2') || queryNorm.includes('subcategoria')) result.level = 'N2'; // Default subcat to N2 unless specified
    else if (queryNorm.includes('nivel 3') || queryNorm.includes('n3')) result.level = 'N3';
    else if (queryNorm.includes('nivel 4') || queryNorm.includes('n4')) result.level = 'N4';

    // Target Level (what we are grouping BY or composing OF)
    // e.g. "Quais subcategorias do nível N3..." -> level=N3 (implicit target)
    // e.g. "Compoem a categoria pai..."

    // Refinement: If user asks "Subcategorias de X", X is the Parent, Subcategories are the target.
    // We'll infer levels based on the matched Category's level later if needed.

    // 4. Extract Category (Fuzzy Match against Dataset)
    // Collect all unique Categories from dataset
    const categories = new Set<string>();
    items.forEach(i => {
        if (i.N1) categories.add(i.N1);
        if (i.N2) categories.add(i.N2);
        if (i.N3) categories.add(i.N3);
        if (i.N4) categories.add(i.N4);
    });

    const uniqueCats = Array.from(categories);
    const qTokens = queryNorm.split(/[\s,.?!]+/);

    // Score Categories
    let bestCat = '';
    let bestScore = Infinity;
    let longestLen = 0;

    uniqueCats.forEach(cat => {
        if (!cat) return;
        const cNorm = normalize(cat);
        const cLen = cNorm.length;
        if (cLen < 3) return;

        // Direct containment (Strongest)
        if (queryNorm.includes(cNorm)) {
            // Prefer the longest match (e.g. "Software" vs "Software de Gestão")
            if (cLen > longestLen) {
                longestLen = cLen;
                bestCat = cat; // Return original casing
                bestScore = 0;
            }
        }
        // Fuzzy Match (only if no direct match found yet, or to find specific close variations)
        else if (bestScore > 0) { // Only search fuzzy if perfect match not found
            // Allow 1 edit for short words, 2 for long
            const maxEdits = cLen > 6 ? 2 : 1;

            // Check if any token in query matches the category
            // Issue: "Indiretos" consists of 1 word. "Material de Escritorio" has 3.
            // We need to check if the category string *roughly* appears in the query.

            // Simplified Fuzzy: Check if any big word in the category appears in the query roughly
            // This is heuristic. Ideally we slide a window, but token matching is fast.
            const catTokens = cNorm.split(/\s+/);
            let matchCount = 0;
            catTokens.forEach(ct => {
                if (ct.length < 3) return; // skip 'de', 'e'
                // FIX: Skip short query tokens too (prevent "as" -> "Gás")
                const tokenMatch = qTokens.some(qt => qt.length >= 3 && levenshtein(qt, ct) <= 1);
                if (tokenMatch) matchCount++;
            });

            // If all significant tokens match
            const sigTokens = catTokens.filter(t => t.length >= 3).length;
            if (sigTokens > 0 && matchCount === sigTokens) {
                // It's a match candidate
                bestCat = cat;
                bestScore = 1; // Fuzzy match priority
            }
            // Single word fallback (e.g. "Manutencao")
            else if (sigTokens === 1 && catTokens.length === 1) {
                const dist = levenshtein(queryNorm, cNorm); // Too broad? No, queryNorm is the whole sentence.
                // Compare against tokens
                const tokenDist = Math.min(...qTokens.map(t => levenshtein(t, cNorm)));
                if (tokenDist <= maxEdits) {
                    bestCat = cat;
                    bestScore = 1;
                }
            }
        }
    });

    if (bestCat) {
        result.category = bestCat;
    }

    // 5. Extract Threshold (e.g. descrições com menos de N caracteres)
    const thresholdMatch = queryNorm.match(/menos de (\d+) (?:caracteres|letras)/);
    if (thresholdMatch) {
        result.threshold = parseInt(thresholdMatch[1], 10);
    }

    return result;
}
