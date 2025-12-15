# Smart Context - Local RAG System

O Smart Context é um sistema de **Retrieval-Augmented Generation (RAG) local** que enriquece as queries do usuário com dados relevantes antes de enviar ao Copilot Studio.

---

## Visão Geral

```mermaid
flowchart LR
    A[Query do Usuário] --> B[Entity Extractor]
    B --> C[Intent Router]
    C --> D[Execution Engine]
    D --> E[Context Payload]
    E --> F[Mensagem Enriquecida]
    F --> G[Copilot Studio]
```

---

## Módulos

### 1. Entity Extractor (`entity-extractor.ts`)

Extrai entidades relevantes da query do usuário.

**Entidades Reconhecidas**:

| Entidade | Exemplo | Resultado |
|----------|---------|-----------|
| `category` | "itens de Software" | `"Software"` |
| `level` | "nível N2" | `"N2"` |
| `number` | "Top 5", "10 exemplos" | `5`, `10` |
| `term` | `termo "manutenção"` | `"manutenção"` |
| `targetType` | "itens", "categorias" | `"item"`, `"category"` |
| `status` | "únicos", "ambíguos" | `"unique"`, `"ambiguous"` |
| `threshold` | "menos de 5 caracteres" | `5` |

**Algoritmos**:
- **Fuzzy Matching**: Usa distância de Levenshtein para encontrar categorias similares
- **Normalização**: Remove acentos e converte para minúsculas
- **Token Matching**: Compara tokens da query com tokens das categorias

---

### 2. Intent Router (`intent-router.ts`)

Identifica a intenção do usuário através de padrões regex.

**Intents Suportados**:

| Intent | Trigger Patterns | Exemplo |
|--------|------------------|---------|
| `OUTLIER_DETECTION` | "menos de X caracteres" | "descrições curtas" |
| `PARETO_ANALYSIS` | "pareto", "curva a", "80/20" | "análise de pareto" |
| `GAP_ANALYSIS` | "sem subcategorias" | "categorias órfãs" |
| `TERM_SEARCH` | "contém termo X" | "itens com 'papel'" |
| `TOP_N_RANKING` | "top N", "maiores" | "top 10 categorias" |
| `BOTTOM_N_RANKING` | "menores", "apenas 1" | "categorias com 1 item" |
| `HIERARCHY_LOOKUP` | "hierarquia completa" | "mostrar caminho" |
| `DISTRIBUTION` | "distribuição", "percentual" | "% por categoria" |
| `COUNT_FILTERED` | "quantos itens" | "quantas linhas" |
| `CATEGORY_LOOKUP` | "liste", "exemplos" | "amostra de Facilities" |

---

### 3. Execution Engine (`execution-engine.ts`)

Executa a intent identificada e gera o payload de contexto.

**Operações por Intent**:

#### CATEGORY_LOOKUP
```javascript
// Retorna amostra de itens da categoria
{
  intent: 'CATEGORY_LOOKUP',
  data: {
    category: 'Software',
    totalCount: 150,
    sample: [...5 itens aleatórios...]
  },
  instructions: 'Analise os itens desta categoria...'
}
```

#### TOP_N_RANKING
```javascript
// Retorna ranking das N maiores categorias
{
  intent: 'TOP_N_RANKING',
  data: {
    ranking: [
      { category: 'Facilities', count: 450 },
      { category: 'MRO', count: 320 },
      ...
    ]
  },
  instructions: 'Apresente o ranking formatado...'
}
```

#### PARETO_ANALYSIS
```javascript
// Calcula curva ABC
{
  intent: 'PARETO_ANALYSIS',
  data: {
    curveA: { categories: [...], percentage: 80 },
    curveB: { categories: [...], percentage: 15 },
    curveC: { categories: [...], percentage: 5 }
  }
}
```

---

## Fluxo de Uso

### No useCopilot

```typescript
const sendUserMessage = async () => {
    // 1. Gerar Smart Context
    const contextPayload = generateSmartContext(userMessage, activeSession?.items || [])
    
    // 2. Formatar mensagem enriquecida
    let messageToSend = userMessage
    if (contextPayload) {
        messageToSend = formatSmartContextMessage(userMessage, contextPayload)
    }
    
    // 3. Enviar ao Copilot
    await apiClient.sendMessageToCopilot(conversationId, token, messageToSend)
}
```

### Formato da Mensagem Enriquecida

```markdown
ATUE COMO UM ANALISTA DE DADOS SÊNIOR.
Sua tarefa é analisar os dados JSON fornecidos abaixo e responder à pergunta do usuário.

INSTRUÇÕES OBRIGATÓRIAS:
1. Analise os dados fornecidos nesta mensagem. NÃO peça mais informações.
2. Use APENAS os dados fornecidos no bloco JSON.
3. Responda em Português do Brasil de forma clara e direta.
4. [Instruções específicas do intent]

DADOS DA ANÁLISE(JSON):
```json
{
  "intent": "TOP_N_RANKING",
  "data": {...}
}
```

PERGUNTA DO USUÁRIO:
"Top 10 categorias com mais itens"
```

---

## Tipos

```typescript
// types.ts
export enum IntentType {
    CATEGORY_LOOKUP = 'CATEGORY_LOOKUP',
    TOP_N_RANKING = 'TOP_N_RANKING',
    BOTTOM_N_RANKING = 'BOTTOM_N_RANKING',
    HIERARCHY_LOOKUP = 'HIERARCHY_LOOKUP',
    DISTRIBUTION = 'DISTRIBUTION',
    OUTLIER_DETECTION = 'OUTLIER_DETECTION',
    GAP_ANALYSIS = 'GAP_ANALYSIS',
    PARETO_ANALYSIS = 'PARETO_ANALYSIS',
    TERM_SEARCH = 'TERM_SEARCH',
    TERM_EXCEPTION = 'TERM_EXCEPTION',
    COUNT_FILTERED = 'COUNT_FILTERED',
    UNKNOWN = 'UNKNOWN'
}

export interface ContextPayload {
    intent: IntentType
    data: any
    instructions: string
}

export interface SmartContextQuery {
    category?: string
    level?: 'N1' | 'N2' | 'N3' | 'N4'
    targetType?: 'item' | 'category' | 'word'
    number?: number
    term?: string
    threshold?: number
    status?: 'unique' | 'ambiguous' | 'unclassified' | 'all'
}
```

---

## Exemplos de Queries

| Query do Usuário | Intent Detectado | Entidades |
|------------------|------------------|-----------|
| "Top 10 categorias N2" | TOP_N_RANKING | level=N2, number=10 |
| "Itens de Software" | CATEGORY_LOOKUP | category=Software |
| "Descrições com menos de 5 caracteres" | OUTLIER_DETECTION | threshold=5 |
| "Quais itens contém 'papel'" | TERM_SEARCH | term=papel |
| "Análise de Pareto" | PARETO_ANALYSIS | - |
| "Distribuição por N1" | DISTRIBUTION | level=N1 |

---

## Extensão

Para adicionar novas intents:

1. Adicione ao enum `IntentType` em `types.ts`
2. Adicione padrões regex em `intent-router.ts`
3. Implemente a lógica em `execution-engine.ts`
