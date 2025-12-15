# Componentes

Esta documentação descreve os principais componentes React do frontend.

---

## Estrutura

```
components/
├── FileUpload.tsx        # Upload genérico de arquivos
├── chat/
│   ├── ChatMessage.tsx   # Mensagem individual do chat
│   └── ChatInput.tsx     # Campo de entrada do chat
├── taxonomy/
│   ├── SessionSidebar.tsx # Sidebar com lista de sessões
│   ├── DownloadCard.tsx   # Card de download do arquivo
│   ├── SectorSelect.tsx   # Seletor de setor
│   ├── ClassifyTab.tsx    # Aba de classificação
│   ├── TrainTab.tsx       # Aba de treinamento
│   └── ModelsTab.tsx      # Aba de gerenciamento de modelos
└── ui/
    ├── Button.tsx         # Botão reutilizável
    ├── Card.tsx           # Container card
    └── Tabs.tsx           # Navegação por abas
```

---

## Chat Components

### ChatMessage

Renderiza uma mensagem individual no chat.

**Props**:
```typescript
interface ChatMessageProps {
    message: Message
    isUser: boolean
}

interface Message {
    text: string
    timestamp?: Date
    from: 'user' | 'bot'
}
```

**Características**:
- Avatares diferenciados (usuário: Navy, bot: agent-icon)
- Suporte a Markdown com estilos customizados
- Bubbles com cantos arredondados (exceto canto interno)
- Animação de fade-in
- Bordas com tom azulado harmonizado

**Loading State**:
```tsx
export function ChatMessageLoading() {
    // Exibe 3 dots animados estilo "thinking"
}
```

---

### Chat Header Actions (New)

O cabeçalho do chat agora inclui um botão de fechamento (X).

- **Botão Fechar**: Reseta a sessão ativa (`setActiveSessionId(null)`).
- **Comportamento**: Retorna o usuário para a tela inicial de abas (Classify/Train/Models) sem perder o histórico (que persiste no storage).

### ChatInput

Campo de entrada estilo Mac Spotlight.

**Props**:
```typescript
interface ChatInputProps {
    value: string
    onChange: (value: string) => void
    onSubmit: () => void
    isLoading?: boolean
    placeholder?: string
    disabled?: boolean
}
```

**Características**:
- Input flutuante com sombra
- Botão de envio integrado (Navy)
- Animação de "thinking" durante loading
- Submissão via Enter ou clique

---

## Taxonomy Components

### SessionSidebar

Lista de sessões com histórico persistido.

**Props**:
```typescript
interface SessionSidebarProps {
    sessions: TaxonomySession[]
    activeSessionId: string | null
    onSessionSelect: (id: string) => void
    onNewUpload: () => void
    onDeleteSession?: (id: string) => void
    onClearHistory?: () => void
}
```

**Características**:
- Background Navy Blue gradient
- Ícones semi-transparentes
- Glassmorphism no item ativo
- Botão "Nova Taxonomia" fixo no bottom
- **Opção de deletar sessão individual**
- **Opção de limpar todo histórico**

---

### ClassifyTab

Aba de classificação de itens com pré-validação.

**Props**:
```typescript
interface ClassifyTabProps {
    onFileSelect: (file: File, fileContent: string, hierarchyContent?: string) => void
    isProcessing: boolean
}
```

**Layout**:
- Duas colunas lado a lado
- **Esquerda**: Upload do arquivo base (obrigatório)
- **Direita**: Upload da hierarquia customizada (opcional)

**Validações**:

| Arquivo | Validação | Status |
|---------|-----------|--------|
| Base | Coluna `Descrição` | ✅ Obrigatório |
| Base | Coluna `SKU` | ⚠️ Opcional |
| Base | Qtd de itens > 0 | ✅ Obrigatório |
| Hierarquia | Colunas `N1, N2, N3, N4` | ✅ Obrigatório |
| Hierarquia | Categorias N4 únicas | ℹ️ Informativo |

**Semáforo Visual**:
- 🟢 Verde: Todos os checks OK
- 🟡 Amarelo: Warnings (pode prosseguir)
- 🔴 Vermelho: Erros (bloqueado)

**Sub-componentes**:
- `ValidationCard`: Exibe resultado da validação com semáforo

---

### DownloadCard

Card de download do arquivo classificado.

**Props**:
```typescript
interface DownloadCardProps {
    downloadUrl: string
    downloadFilename: string
}
```

**Características**:
- Avatar do AI
- Ícone de Excel
- Header de sucesso com checkmark
- Botão de download slim Navy pill
- Borda azulada harmonizada com fundo

---

### TrainTab

Aba de treinamento de modelos ML.

**Sub-componentes**:
1. `UploadStep` - Upload do arquivo de treino
2. `PreviewStep` - Validação e preview dos dados
3. `TrainingStep` - Processamento (loading)
4. `ResultStep` - Resultado e conclusão (opção de treinar outro)

**States**:
```typescript
trainingStep: 'upload' | 'preview' | 'training' | 'result'
```

**Validações**:
- Estrutura do arquivo (colunas obrigatórias)
- Completude dos dados
- Volume mínimo de dados

---

### ModelsTab

Gerenciamento de versões de modelos.

**Props**:
```typescript
interface ModelsTabProps {
    sector: string
    modelHistory: ModelHistoryEntry[]
    isProcessing: boolean
    onRefresh: () => void
    onRestoreModel: (versionId: string) => void
}
```

**Características**:
- Tabela de histórico de versões
- Badge "Ativo" para versão atual (verde)

### ModelViewerOverlay

Overlay detalhado para visualização do modelo.

**Props**:
```typescript
interface ModelViewerOverlayProps {
    sector: string
    versionId: string // Versão a visualizar
    // ...
}
```

**Features**:
1.  **Comparação Visual**: Usa componente `DiffIndicator` para mostrar variação percentual/absoluta contra versão anterior.
    *   Seta Verde (▲) e Vermelha (▼)
    *   Suporte para Acurácia, F1, Samples, e contagens N1-N4.
2.  **Abas**:
    *   **Árvore**: Visualização hierárquica com diffs em cada nível.
    *   **Estatísticas**: KPIs do modelo e gráfico.
    *   **Dados**: Tabela paginada com colunas N1-N4 e busca.
3.  **Proteção**:
    *   Bloqueia exclusão da última versão restante.
    *   Bloqueia exclusão da versão ativa (auto-ativa anterior).

---

## UI Base Components

### Button

Botão com variantes.

**Props**:
```typescript
interface ButtonProps {
    variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
    size?: 'sm' | 'md' | 'lg'
    isLoading?: boolean
    disabled?: boolean
    children: React.ReactNode
    onClick?: () => void
    title?: string // Tooltip
}
```

**Variantes**:
- `primary`: Navy Blue sólido
- `secondary`: Outline Navy
- `ghost`: Transparente com hover
- `danger`: Hover vermelho (usado para fechar/deletar)

---

### Card

Container com glassmorphism.

**Props**:
```typescript
interface CardProps {
    variant?: 'default' | 'glass' | 'bordered'
    className?: string
    children: React.ReactNode
}
```

---

### Tabs

Navegação por abas com colunas iguais.

**Características**:
- **Layout Grid**: Usa `grid-cols-3` para garantir larguras matematicamente iguais.
- **Responsivo**: Adapta-se ao container pai.

**Props**:
```typescript
interface TabsProps {
    tabs: { id: string; label: string }[]
    activeTab: string
    onChange: (tabId: string) => void
}
```

---

## Padrão de Componentização

### Princípios Seguidos

1. **Single Responsibility**: Cada componente faz uma coisa bem
2. **Props Interface**: Tipagem explícita com TypeScript
3. **Composição**: Componentes pequenos compostos em maiores
4. **Stateless Preference**: Estado elevado para hooks quando possível
5. **Callbacks para ações**: onAction props para comunicação com parent

### Exemplo de Uso

```tsx
// taxonomy.tsx
<SessionSidebar
    sessions={sessions}
    activeSessionId={activeSessionId}
    onSessionSelect={setActiveSessionId}
    onNewUpload={handleNewUpload}
    onDeleteSession={handleDeleteSession}
    onClearHistory={handleClearHistory}
/>

<ChatMessage
    message={msg}
    isUser={msg.from === 'user'}
/>

<ChatInput
    value={userMessage}
    onChange={setUserMessage}
    onSubmit={sendUserMessage}
    isLoading={isSending}
/>
```

---

## Design System

### Cores Principais

| Token | Valor | Uso |
|-------|-------|-----|
| Navy Primary | `#102a43` | Sidebar, botões |
| Navy Dark | `#0d1f3c` | Gradientes |
| Cyan Accent | `#14919b` | Status ativo, CTAs |
| Off-White | `#F5F7FA` | Background |
| Ice Blue | `#E8F0F5` | Background taxonomy |

### Bordas

Componentes usam `border-[#102a43]/8` para harmonizar com fundo azulado.
