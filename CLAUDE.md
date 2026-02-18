# CLAUDE.md - Azure Spend Analysis AI Agent

## Visao Geral do Projeto

Plataforma inteligente de classificacao de gastos corporativos que categoriza automaticamente dados de compras usando abordagem hibrida: Machine Learning (scikit-learn), dicionario de keywords (regex) e fallback via LLM (Grok/xAI). Inclui Copilot integrado com sistema RAG client-side para analise conversacional dos dados classificados.

**Dominio**: Spend Analysis / Procurement / Classificacao taxonomica N1-N4
**Cliente**: PG Consultoria - AI Team

---

## Arquitetura

### Stack Tecnologico

| Camada | Tecnologia |
|--------|-----------|
| Backend | Azure Functions v2 (Python 3.9+) |
| Frontend | Next.js 14 + TypeScript + React 18 + TailwindCSS 3.4 |
| ML | scikit-learn (TF-IDF + Logistic Regression) |
| LLM | Grok/xAI API (`grok-4-1-fast-reasoning`) |
| Chat | Microsoft Copilot Studio (Direct Line API) |
| Storage | Azure File Share (`/mount/models`), IndexedDB (client) |
| CI/CD | GitHub Actions -> Azure Static Web Apps |
| Integracoes | Power Automate (SharePoint), Copilot Studio |

### Fluxo de Classificacao (Pipeline Hibrido)

```
Descricao do item
  -> Normalizacao de texto (lowercase, acentos, abreviacoes, noise words)
  -> Passo 1: ML Classifier (TF-IDF + LogisticRegression)
     -> Confianca >= 0.45: "Unico" (usa ML)
     -> Confianca 0.25-0.44: "Ambiguo" (top 3 ML + tenta dicionario)
     -> Confianca < 0.25: fallback para dicionario
  -> Passo 2: Dictionary Classifier (regex/keywords do Spend_Taxonomy.xlsx)
     -> Match unico: "Unico" (usa dicionario)
     -> Multiplos matches: "Ambiguo"
     -> Sem match: "Nenhum"
  -> Passo 3: LLM Fallback (Grok) para itens "Nenhum" (batch async, 20 workers)
     -> Com hierarquia customizada: prompt inclui arvore compacta (N1>N2>N3>[N4s]) + restricao obrigatoria
     -> Hierarquia no system message (fixo entre chamadas), itens no user message
  -> Passo 4: Validacao local contra hierarquia customizada (sem LLM adicional)
     -> Exact match (case-insensitive) na hierarquia → aplica
     -> Fuzzy match (difflib, cutoff=0.6) → aplica
     -> Sem match → marca como "Nenhum"
  -> Resultado: {N1, N2, N3, N4, status, source, confidence, matched_terms}
```

### Processamento Assincrono

- Arquivos sao submetidos via `SubmitTaxonomyJob` e divididos em chunks de 500 linhas
- Worker processa chunks via timer trigger (a cada 15 segundos) com time budget de 20 min por ciclo
- **Round-robin entre jobs**: worker processa 1 chunk por job ativo, ciclando entre todos, ao inves de processar todos os chunks de um job antes de passar ao proximo. Isso garante que jobs pequenos nao ficam bloqueados por jobs grandes
- **Auto-limpeza**: jobs PROCESSING ha mais de 1 hora sao automaticamente marcados como ERROR
- Jobs armazenados como arquivos JSON em `models/taxonomy_jobs/`
- Frontend faz polling via `GetTaxonomyJobStatus` a cada 5 segundos
- Suporta ate 50K linhas por arquivo e multiplos jobs simultaneos
- Na consolidacao, dados originais (descricoes, valores) sao unidos com colunas de classificacao no Excel de download

---

## Estrutura do Projeto

```
/
├── function_app.py              # Entry point - endpoints HTTP + timer worker (round-robin) + helpers
├── run_local_worker.py          # Worker local com mock do Azure Functions
├── src/
│   ├── taxonomy_engine.py       # Classificacao por dicionario (regex/keywords)
│   ├── hybrid_classifier.py     # Orquestrador ML + Dicionario + fallback
│   ├── ml_classifier.py         # Preditor ML (TF-IDF + LogisticRegression)
│   ├── llm_classifier.py        # Integracao Grok/xAI (async, 20 workers)
│   ├── model_trainer.py         # Pipeline de treinamento com versionamento
│   ├── taxonomy_mapper.py       # Mapeamento de hierarquia customizada
│   ├── preprocessing.py         # Normalizacao de texto e features
│   ├── core_classification.py   # Orquestrador de chunks (3 passos)
│   └── memory_engine.py         # Gerenciamento de memoria/regras
├── models/                      # Artefatos ML por setor
│   ├── {setor}/                 # Ex: varejo/, educacional/
│   │   ├── classifier.pkl       # Modelo ativo
│   │   ├── tfidf_vectorizer.pkl # Vocabulario TF-IDF
│   │   ├── label_encoder.pkl    # Encoder de categorias
│   │   ├── n4_hierarchy.json    # Mapeamento N4 -> N1,N2,N3
│   │   ├── model_history.json   # Historico de versoes
│   │   └── versions/            # Versoes anteriores (max 3)
│   └── taxonomy_jobs/           # Fila de jobs async (filesystem)
├── data/
│   └── taxonomy/
│       └── Spend_Taxonomy.xlsx  # Dicionario master de classificacao
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── index.tsx        # Landing page
│   │   │   └── taxonomy.tsx     # Pagina principal da aplicacao
│   │   ├── components/
│   │   │   ├── taxonomy/        # Componentes de classificacao (ClassifyTab, TrainTab, ModelsTab, etc.)
│   │   │   ├── chat/            # UI do Copilot (ChatInput, ChatMessage)
│   │   │   ├── ui/              # Design system (Button, Card, Tabs, etc.)
│   │   │   └── FileUpload.tsx   # Upload de arquivos
│   │   ├── hooks/
│   │   │   ├── useTaxonomySession.ts  # Lifecycle de sessao
│   │   │   ├── useCopilot.ts          # Integracao Copilot
│   │   │   └── useModelTraining.ts    # Estado de treinamento
│   │   └── lib/
│   │       ├── api.ts           # Cliente HTTP (axios)
│   │       ├── database.ts      # IndexedDB (sessoes)
│   │       ├── design-tokens.ts # Tokens de design
│   │       └── smart-context/   # Sistema RAG client-side
│   │           ├── index.ts     # Orquestrador principal
│   │           ├── entity-extractor.ts  # NLP para entidades
│   │           ├── intent-router.ts     # Classificacao de intent
│   │           └── execution-engine.ts  # Agregacao de dados
│   └── package.json
├── docs/                        # Documentacao detalhada
├── .github/workflows/           # CI/CD (Azure Static Web Apps)
├── host.json                    # Config Azure Functions (timeout 30min)
├── requirements.txt             # Dependencias Python
└── staticwebapp.config.json     # Config routing SWA
```

---

## Endpoints da API

| Endpoint | Metodo | Descricao |
|----------|--------|-----------|
| `/api/SubmitTaxonomyJob` | POST | Submete job de classificacao async (retorna jobId) |
| `/api/GetTaxonomyJobStatus` | GET | Poll status do job (PENDING/PROCESSING/COMPLETED/ERROR) |
| `/api/TrainModel` | POST | Treina novo modelo ML para setor |
| `/api/GetModelHistory` | GET | Historico de versoes do modelo |
| `/api/SetActiveModel` | POST | Rollback para versao anterior |
| `/api/GetModelInfo` | GET | Info detalhada do modelo |
| `/api/GetTrainingData` | GET | Browser paginado de dados de treino |
| `/api/DeleteTrainingData` | POST | Limpa dados de treino |
| `/api/get-token` | GET | Token Direct Line para Copilot |
| `/api/ProcessTaxonomy` | POST | **DEPRECATED** (retorna 410) |

---

## Constantes e Thresholds Importantes

```python
# Classificacao ML (hybrid_classifier.py)
ML_CONFIDENCE_UNIQUE = 0.45       # Confianca minima para "Unico"
ML_CONFIDENCE_AMBIGUOUS = 0.25    # Abaixo disso, fallback para dicionario

# Analytics (taxonomy_engine.py)
PARETO_CLASS_A_THRESHOLD = 0.80   # 80% acumulado = Classe A
PARETO_CLASS_B_THRESHOLD = 0.95   # 95% acumulado = Classe B
LRU_CACHE_SIZE = 10000            # Cache de descricoes normalizadas
MIN_WORD_LENGTH_FOR_GAPS = 3      # Comprimento minimo para gap analysis
TOP_GAPS_COUNT = 20               # Top N gaps retornados
TOP_AMBIGUITY_COUNT = 20          # Top N ambiguidades retornadas

# Treinamento (model_trainer.py)
MIN_EXAMPLES_PER_CATEGORY = 5     # Minimo de exemplos por N4
TFIDF_MAX_FEATURES = 5000         # Features do vocabulario
TFIDF_NGRAMS = (1, 2)             # Unigramas + bigramas
TRAIN_VAL_SPLIT = 0.2             # 80/20 estratificado
MAX_MODEL_VERSIONS = 3            # Maximo de versoes retidas

# Processamento async (function_app.py)
CHUNK_SIZE = 500                  # Linhas por chunk
JOB_TIMEOUT_MINUTES = 20          # Budget interno do worker (round-robin)
STALE_JOB_THRESHOLD = 3600        # 1 hora - jobs PROCESSING alem disso viram ERROR

# LLM (llm_classifier.py)
LLM_BATCH_SIZE = 40               # Itens por chamada ao Grok
LLM_CONCURRENT_WORKERS = 20       # Threads paralelas
LLM_TIMEOUT_SECONDS = 90          # Timeout por chamada
LLM_MAX_RETRIES = 2               # Retries com backoff exponencial

# Hierarquia customizada (llm_classifier.py + core_classification.py)
HIERARCHY_FORMAT = "compact_tree"  # Formato arvore agrupado (N1>N2>N3>[N4s]) - ~60-70% menos tokens
HIERARCHY_DATA_STRUCTURE = "list"  # Lista de dicts (preserva N4s duplicados como "Materiais OEM" em multiplas marcas)
HIERARCHY_PROMPT = "dedicated"     # Prompt separado para custom_hierarchy (sem exemplo generico Tubo/MRO)
PASS3_LLM_SEMANTIC_MAP = False    # Pass 3 agora usa validacao local (sem LLM adicional)
```

---

## Variaveis de Ambiente

```
# Azure Functions
FUNCTIONS_WORKER_RUNTIME=python
AzureWebJobsStorage=UseDevelopmentStorage=true

# Modelos
MODELS_DIR_PATH=               # Override do diretorio de modelos (opcional)
USE_ML_CLASSIFIER=true         # Habilita/desabilita classificador ML

# Grok/xAI
GROK_API_KEY=                  # API key do xAI
GROK_API_ENDPOINT=https://api.x.ai/v1
GROK_MODEL_NAME=grok-4-1-fast-reasoning

# Copilot Studio
DIRECT_LINE_SECRET=            # Token Direct Line

# Power Automate
POWER_AUTOMATE_URL=            # Webhook URL do Flow
POWER_AUTOMATE_API_KEY=        # API key do Flow

# Frontend (.env.local)
NEXT_PUBLIC_API_URL=http://localhost:7071/api
NEXT_PUBLIC_FUNCTION_KEY=
```

---

## Desenvolvimento Local

### Backend
```bash
# Instalar dependencias
pip install -r requirements.txt

# Rodar Azure Functions localmente (requer Azure Functions Core Tools)
func start

# Ou rodar worker local diretamente
python run_local_worker.py
```

### Frontend
```bash
cd frontend
npm install
npm run dev   # Next.js em http://localhost:3000
```

### URLs de Producao
- **Frontend**: Azure Static Web Apps (deploy automatico via GitHub Actions no push para main)
- **Backend**: `https://az-pg-spend-analysis-ai-agent.azurewebsites.net/api`

---

## Convencoes de Codigo

### Python (Backend)
- Modulos em `src/` com responsabilidade unica
- Funcoes de normalizacao centralizadas em `preprocessing.py` (ATENCAO: existe duplicacao com `taxonomy_engine.py` - usar `preprocessing.py` como source of truth)
- Models salvos como `.pkl` (joblib) organizados por setor em `models/{setor}/`
- Logging via `logging` stdlib (nao usar `print()` para logs)
- Imports de modulos `src/` usar formato relativo: `from src.module import func`
- Tratamento de NaN/Infinity em JSON com `safe_json_dumps()` (definido em function_app.py)

### TypeScript (Frontend)
- Hooks customizados em `frontend/src/hooks/` para logica de estado
- API client centralizado em `frontend/src/lib/api.ts`
- Componentes organizados por feature em `frontend/src/components/taxonomy/`
- Design tokens em `frontend/src/lib/design-tokens.ts`
- Persistencia client-side via IndexedDB (wrapper em `frontend/src/lib/database.ts`)
- TailwindCSS para estilizacao
- Download de arquivos usa conversao **sob demanda** no clique: base64 → `atob()` + `Uint8Array` → Blob → anchor programatico com `link.click()`. NAO usar blob URLs pre-criados (`URL.createObjectURL`) nem `fetch(dataUrl)` — ambos falham silenciosamente em certos browsers/contextos
- `DownloadCard` recebe `fileContentBase64` (string) e gera o blob no momento do clique. NAO depende de blob URLs em estado/memoria
- Sessoes armazenam `fileContentBase64` tanto em runtime (React state) quanto em persistencia (IndexedDB). O campo `downloadUrl` (blob URL) foi removido da arquitetura

### Nomenclatura
- Niveis taxonomicos: N1 (mais alto) -> N4 (mais granular)
- Status de classificacao: "Unico", "Ambiguo", "Nenhum"
- Fontes de classificacao: "ML", "Dictionary", "LLM", "LLM (Batch)", "Custom (via ...)", "Custom/fuzzy (via ...)", "None"
- Setores: lowercase (ex: "varejo", "educacional")

---

## Pontos de Atencao Arquitetural

### Problemas Conhecidos (Divida Tecnica)

1. **God File**: `function_app.py` (~1600 linhas) contem todos os endpoints + logica de negocio inline. Idealmente deveria ser dividido em Azure Function Blueprints
2. **Duplicacao de `normalize_text`**: Existe em `preprocessing.py` E `taxonomy_engine.py` - manter sincronizados ou eliminar duplicacao
3. **sys.path manipulation**: `hybrid_classifier.py` manipula `sys.path` para imports - indica estrutura de pacotes fragil
4. **File-based job queue**: Jobs async usam filesystem (`taxonomy_jobs/`), o que nao escala horizontalmente. Considerar Azure Queue Storage
5. **Seguranca**: Todos os endpoints usam `AuthLevel.ANONYMOUS` e CORS `*`. Em producao, restringir
6. **Sem testes automatizados**: Nao ha suite de testes. Prioridade alta para classificadores e normalizacao
7. **Cache in-memory**: `_MODEL_CACHE` em `ml_classifier.py` nao persiste entre instancias Azure Functions
8. **Row-by-row processing**: `core_classification.py` usa `iterrows()` para classificacao - poderia ser vetorizado para ML predictions em batch
9. **Endpoint deprecated**: `/api/ProcessTaxonomy` retorna 410 - pode ser removido
10. ~~**Sem limpeza automatica de jobs**~~: **RESOLVIDO** - Worker agora marca jobs PROCESSING > 1h como ERROR automaticamente (`_cleanup_stale_jobs`)
11. ~~**Worker sequencial**~~: **RESOLVIDO** - Worker agora usa round-robin entre jobs ativos, processando 1 chunk por job ciclicamente. Jobs pequenos terminam rapido mesmo com jobs grandes em paralelo

### Ao Modificar Codigo

- **Thresholds de confianca** (0.45/0.25 em `hybrid_classifier.py`) afetam TODA a classificacao - testar com dados reais antes de alterar
- **normalize_text()** e usado em treinamento E predicao - alteracoes DEVEM ser aplicadas em ambos os fluxos senao os modelos quebram
- **Artefatos ML** (.pkl) sao acoplados a versao do scikit-learn - nao atualizar scikit-learn sem retreinar modelos
- **Spend_Taxonomy.xlsx** e o dicionario master - alteracoes afetam a classificacao por dicionario imediatamente
- **Prompts do Grok** em `llm_classifier.py` afetam qualidade da classificacao LLM - versionar alteracoes. Quando `custom_hierarchy` presente, usa prompt SEPARADO (sem exemplo generico Tubo/MRO) com instrucoes explicitas sobre niveis da arvore. Prompt sem hierarquia nao muda
- **Hierarquia customizada**: parseada como LISTA de dicts (nao dict keyed por N4) para preservar N4s duplicados (ex: "Materiais OEM" em 18 marcas). `_format_hierarchy_compact()` aceita lista ou dict (backward compat)
- **Hierarquia customizada no worker**: parseada UMA VEZ por job em `_get_active_jobs()` e armazenada em `job_info["custom_hierarchy"]`. NAO parsear novamente em `_process_single_chunk()`
- **IndexedDB** no frontend armazena sessoes completas incluindo dados classificados - cuidado com o volume
- **Download de arquivos** no frontend: NUNCA usar blob URLs pre-criados (`URL.createObjectURL`) para download — eles se tornam invalidos (GC, refresh, ciclo de vida do browser). SEMPRE converter base64→Blob **no momento do clique** com `atob()` + `Uint8Array` + anchor programatico (`link.click()`). O `DownloadCard` recebe `fileContentBase64` diretamente, NAO um blob URL
- **Consolidacao do worker** (`function_app.py`): ao gerar Excel de download, DEVE unir dados originais (chunk_X.json) com resultados de classificacao (result_X.json). Sem isso, o Excel sai sem descricoes
- **Worker helpers** (`function_app.py`): logica do worker esta em funcoes auxiliares prefixadas com `_` (`_cleanup_stale_jobs`, `_get_active_jobs`, `_find_next_chunk`, `_parse_custom_hierarchy`, `_process_single_chunk`, `_consolidate_job`). Manter a logica nessas funcoes e o `ProcessTaxonomyWorker` como orquestrador enxuto

---

## Regras de Commit

- NUNCA adicionar "Co-Authored-By" nos commits. Fazer commits simples sem co-autor.
- Mensagens em portugues, descritivas do que foi alterado
- Prefixos sugeridos: `Fix`, `Ajuste`, `Adicionando`, `Refactor`

---

## Deployment

- Push para `main` dispara deploy automatico via GitHub Actions
- Frontend: Azure Static Web Apps (build Next.js com output estatico)
- Backend: Azure Functions App (deploy separado via `func azure functionapp publish az-pg-spend-analysis-ai-agent`)
- Modelos ML sao copiados do pacote para Azure File Share no bootstrap (`/mount/models`)
- Function timeout configurado para 30 minutos em `host.json`

### Infraestrutura Azure

| Recurso | Nome |
|---------|------|
| Function App | `az-pg-spend-analysis-ai-agent` |
| Resource Group | `azpgspendanalysisaiagent` |
| Storage Account | `azpgspendanalysisaiagent` |
| File Share | `models-data` (montado em `/mount/models`) |
| Jobs Path | `taxonomy_jobs/` dentro do File Share |

### Operacoes de Manutencao (Azure CLI)

```bash
# Listar jobs no File Share
az storage file list --share-name models-data --path "taxonomy_jobs" \
  --account-name azpgspendanalysisaiagent --output table

# Verificar status de um job
az storage file download --share-name models-data \
  --path "taxonomy_jobs/{JOB_ID}/status.json" --dest /tmp/status.json \
  --account-name azpgspendanalysisaiagent --no-progress

# Matar job travado (marcar como ERROR)
# NOTA: Worker agora faz auto-limpeza de jobs PROCESSING > 1h automaticamente.
# Intervencao manual so e necessaria para casos urgentes (< 1h):
# 1. Baixar status.json, 2. Editar status para "ERROR", 3. Upload de volta

# Reiniciar Function App (mata workers em execucao)
az functionapp restart --name az-pg-spend-analysis-ai-agent \
  --resource-group azpgspendanalysisaiagent
```

### Bugs Historicos Resolvidos

| Data | Bug | Causa | Fix |
|------|-----|-------|-----|
| 2026-02-16 | Timeout em arquivos >5K linhas | LLM batch_size=2 (muito pequeno) + worker sem time budget | batch_size=20, time budget 20min no worker |
| 2026-02-16 | Job novo fica PENDING eternamente | Jobs antigos PROCESSING bloqueavam worker sequencial | Limpeza manual via Azure CLI + restart |
| 2026-02-16 | Download Excel 0KB (v1) | `fetch(dataUrl)` falhava silenciosamente no frontend | Substituido por `atob()` + `Uint8Array` |
| 2026-02-16 | Download Excel 0KB (v2) | Blob URLs pre-criados (`URL.createObjectURL`) se tornavam invalidos antes do clique do usuario | Removido blob URLs; download agora converte base64→Blob sob demanda no clique com anchor programatico |
| 2026-02-16 | Excel download sem descricoes | Consolidacao so incluia colunas de classificacao | Worker agora une chunk_X.json (original) com result_X.json |
| 2026-02-16 | Job novo fica PENDING com jobs simultaneos | Worker sequencial processava todos os chunks de um job antes de passar ao proximo | Refactor para round-robin: 1 chunk por job ciclicamente + auto-limpeza de jobs travados >1h |
| 2026-02-18 | Job com hierarquia customizada ~50min (vs ~15min sem) | Prompt LLM incluia 276 categorias em formato linear (~5500 tokens) + Pass 3 fazia chamadas LLM extras (semantic mapping) sem cache entre chunks | Hierarquia compacta (arvore agrupada, ~1800 tokens) + prompt restritivo + Pass 3 local (exact+fuzzy match sem LLM) + parse hierarquia 1x por job |
| 2026-02-18 | OEM sempre WARTSILA + hierarquia deslocada (N2 como N1) | `_parse_custom_hierarchy()` usava dict keyed por `n4.lower()` (perdia N4s duplicados) + prompt tinha exemplo hardcoded "MRO" como N1 | Hierarquia como lista (preserva duplicatas) + prompt separado para custom_hierarchy sem exemplo enganoso + instrucoes explicitas sobre niveis da arvore |
