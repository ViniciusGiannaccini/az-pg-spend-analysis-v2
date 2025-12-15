# Arquitetura do Frontend

## Overview

O frontend segue uma arquitetura baseada em **hooks customizados** para separação de responsabilidades, com componentes UI reutilizáveis, sistema de **persistência híbrida** (IndexedDB + localStorage) e Smart Context para enriquecimento de queries.

---

## Padrão Arquitetural

```
┌─────────────────────────────────────────────────────────────┐
│                        PAGES                                │
│  (index.tsx, taxonomy.tsx)                                  │
│  - Orquestração                                             │
│  - Layout                                                   │
└───────────────────────┬─────────────────────────────────────┘
                        │ usa
┌───────────────────────▼─────────────────────────────────────┐
│                    CUSTOM HOOKS                             │
│  useTaxonomySession  │  useCopilot  │  useModelTraining     │
│  - Estado            │  - Chat      │  - Treinamento        │
│  - Sessões           │  - IA        │  - Modelos ML         │
│  - IndexedDB         │  - localStorage │                    │
└───────────────────────┬─────────────────────────────────────┘
                        │ usa
┌───────────────────────▼─────────────────────────────────────┐
│                         LIB                                 │
│  api.ts       │  database.ts   │  smart-context/            │
│  - HTTP Client│  - IndexedDB   │  - Entity Extract          │
│  - Endpoints  │  - Sessions    │  - Intent Route            │
│               │                │  - Execution               │
└───────────────────────┬─────────────────────────────────────┘
                        │ renderiza
┌───────────────────────▼─────────────────────────────────────┐
│                     COMPONENTS                              │
│  ui/         │  chat/         │  taxonomy/                  │
│  - Button    │  - ChatMessage │  - SessionSidebar           │
│  - Card      │  - ChatInput   │  - DownloadCard             │
│  - Tabs      │                │  - TrainTab, ModelsTab      │
└─────────────────────────────────────────────────────────────┘
```

---

## Hooks Customizados

### 1. `useTaxonomySession`

**Propósito**: Gerencia o estado de sessões de classificação com persistência.

**Responsabilidades**:
- Lista de sessões ativas (persistidas em IndexedDB)
- Sessão atualmente selecionada
- Upload e processamento de arquivos
- Carregamento de setores do dicionário
- CRUD de sessões

**Estado**:
```typescript
{
  sessions: TaxonomySession[]
  activeSessionId: string | null
  isProcessing: boolean
  sector: string
  sectors: string[]
  isLoadingSectors: boolean
}
```

**Actions**:
```typescript
{
  setSector: (sector: string) => void
  setActiveSessionId: (id: string | null) => void
  handleNewUpload: () => void
  handleFileSelect: (file, content) => Promise<void>
  handleClearHistory: () => void  // Limpa tudo
  handleDeleteSession: (id) => void // Deleta uma sessão
}
```

---

### 2. `useCopilot`

**Propósito**: Comunicação com Microsoft Copilot Studio via Direct Line.

**Responsabilidades**:
- Gerenciamento de conversação (stateless RAG)
- Geração de Executive Summary
- Envio de mensagens com Smart Context
- Fallback para mensagens diretas (saudações)
- Persistência de chat em localStorage
- Polling de respostas

**Características**:
- **Stateless RAG**: Cada mensagem cria nova conversação Direct Line
- **Smart Context**: Enriquece queries com dados relevantes
- **Direct Fallback**: Mensagens sem contexto são enviadas diretamente
- **Auto-persist**: Chat salvo automaticamente via `updateMessages()`

---

### 3. `useModelTraining`

**Propósito**: Gerencia fluxo de treinamento de modelos ML.

**Responsabilidades**:
- Upload de arquivo de treino
- Validação de formato
- Preview de dados
- Execução de treinamento
- Histórico de versões

---

## Persistência de Dados

### Camadas

| Camada | Tecnologia | Dados |
|--------|------------|-------|
| **Sessões** | IndexedDB (`idb`) | TaxonomySession completo |
| **Chat** | localStorage | Messages por sessão |
| **Runtime** | React State | Blob URLs, UI State |

### Módulo `database.ts`

```typescript
// IndexedDB wrapper
import { openDB, DBSchema, IDBPDatabase } from 'idb'

export const saveSession = async (session) => {...}
export const getSession = async (sessionId) => {...}
export const getAllSessions = async () => {...}
export const deleteSession = async (sessionId) => {...}
export const clearAllSessions = async () => {...}
```

---

## Componentes

### UI Base

| Componente | Descrição |
|------------|-----------|
| `Button` | Botão com variantes (primary, secondary, ghost) |
| `Card` | Container com variantes de glassmorphism |
| `Tabs` | Navegação por abas |

### Chat

| Componente | Descrição |
|------------|-----------|
| `ChatMessage` | Renderiza mensagem (user/bot) com Markdown |
| `ChatInput` | Campo de entrada estilo Spotlight |

### Taxonomy

| Componente | Descrição |
|------------|-----------|
| `SessionSidebar` | Lista de sessões com histórico |
| `DownloadCard` | Card de download do arquivo processado |
| `SectorSelect` | Seleção de setor |
| `ClassifyTab` | Aba de classificação |
| `TrainTab` | Aba de treinamento |
| `ModelsTab` | Gerenciamento de versões de modelos |

---

## Design Tokens

O arquivo `design-tokens.ts` centraliza:

- **Cores**: Paleta Navy, Cyan, Off-White (identidade PG)
- **Sombras**: card, lg, input, glow
- **Gradientes**: Primários e de fundo
- **Utilidades Tailwind**: Classes pré-definidas

---

## Fluxo de Dados

```mermaid
flowchart TD
    A[Página Carrega] --> B[getAllSessions → IndexedDB]
    B --> C[Reconstrói blob URLs]
    C --> D[setSessions → React State]
    
    subgraph Classificação
        E[Usuário faz upload base] --> F[validateBaseFile]
        F --> G{Válido?}
        G -->|Não| H[Mostra erros]
        G -->|Sim| I[Mostra semáforo verde]
        
        J[Upload hierarquia opcional] --> K[validateHierarchyFile]
        K --> L{Válido?}
        L -->|Não| M[Mostra erros]
        L -->|Sim| N[Mostra semáforo verde]
        
        I --> O[Botão Classificar habilitado]
        N --> O
        O --> P[handleFileSelect]
    end
    
    P --> Q[processTaxonomy API + customHierarchy]
    Q --> R[Cria TaxonomySession]
    R --> S[saveSession → IndexedDB]
    S --> T[Ativa sessão]
    
    T --> U[getChatFromStorage → localStorage]
    U --> V[Se vazio: generateExecutiveSummary]
    
    W[Usuário envia mensagem] --> X[Smart Context processa]
    X --> Y{Contexto encontrado?}
    Y -->|Sim| Z[executeConversationTurn]
    Y -->|Não| AA[executeDirectMessage]
    Z --> AB[updateMessages]
    AA --> AB
    AB --> AC[saveChatToStorage → localStorage]
    AC --> AD{Usuário clica Fechar}
    AD -->|Sim| AE[setActiveSessionId(null)]
    AE --> A[Retorna à Home das Abas]
```

---

## Dependências Principais

```json
{
  "next": "14.2.3",
  "react": "18.x",
  "typescript": "5.x",
  "axios": "^1.x",
  "xlsx": "^0.18.x",
  "idb": "^8.x",
  "react-markdown": "^9.x"
}
```
