# Endpoints de API

## Overview

A Azure Function expõe 8 endpoints HTTP para classificação, treinamento e gerenciamento de modelos.

**Base URL**: `https://<function-app>.azurewebsites.net/api`

### Autenticação e CORS
Todos os endpoints foram configurados como `AuthLevel.ANONYMOUS` para garantir total compatibilidade com **CORS** (Cross-Origin Resource Sharing) nos navegadores.

- **CORS**: `Access-Control-Allow-Origin: *` é retornado em todas as respostas.
- **API Key**: O frontend envia o header `x-functions-key` por padrão, mas a verificação estrita na gateway da Azure está desabilitada para permitir preflight requests (`OPTIONS`). A segurança deve ser tratada via VNET ou IP Restriction se necessário.

---

## 1. GetDirectLineToken

**GET** `/get-token`

Obtém token temporário para comunicação com Microsoft Copilot Studio via Direct Line.

### Response
```json
{
  "conversationId": "abc123",
  "token": "eyJ...",
  "expires_in": 1800
}
```

### Errors
| Status | Descrição |
|--------|-----------|
| 500 | DIRECT_LINE_SECRET não configurado |

---

## 2. ProcessTaxonomy

**POST** `/ProcessTaxonomy`

Classifica um arquivo Excel/CSV usando o dicionário de taxonomia.

### Request Body
```json
{
  "fileContent": "<base64-encoded-file>",
  "dictionaryContent": "<base64-encoded-dictionary>",
  "sector": "Varejo",
  "originalFilename": "gastos_jan.xlsx",
  "customHierarchy": "<base64-encoded-hierarchy>"
}
```

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| fileContent | string | ✅ | Arquivo a classificar (base64) |
| dictionaryContent | string | ✅ | Spend_Taxonomy.xlsx (base64) |
| sector | string | ✅ | Setor (Varejo, Educacional, etc.) |
| originalFilename | string | ❌ | Nome original do arquivo |
| customHierarchy | string | ❌ | Hierarquia customizada (base64) - substitui árvore padrão |

#### Hierarquia Customizada

Quando `customHierarchy` é fornecido:
1. ML classifica normalmente usando modelo treinado
2. Sistema busca N4 predito na hierarquia customizada
3. Se encontrar → usa N1, N2, N3 da hierarquia do cliente
4. Se não encontrar → tenta 2º e 3º candidatos (fallback)
5. Se nenhum candidato existir → item fica sem classificação

**Colunas esperadas no arquivo de hierarquia**: `N1 | N2 | N3 | N4`

### Response
```json
{
  "status": "success",
  "sessionId": "uuid-v4",
  "fileContent": "<base64-xlsx>",
  "filename": "gastos_jan_classified_20251213_143022.xlsx",
  "summary": {
    "total_linhas": 1000,
    "coluna_descricao_utilizada": "Item_Description",
    "unico": 650,
    "ambiguo": 200,
    "nenhum": 150
  },
  "analytics": {
    "pareto": [...],
    "pareto_N1": [...],
    "pareto_N2": [...],
    "pareto_N3": [...],
    "pareto_N4": [...],
    "gaps": [...],
    "ambiguity": [...]
  },
  "items": [...],
  "timestamp": "20251213_143022",
  "encoding": "base64"
}
```

### Colunas Adicionadas ao Excel

| Coluna | Descrição |
|--------|-----------|
| N1 | Categoria nível 1 |
| N2 | Categoria nível 2 |
| N3 | Categoria nível 3 |
| N4 | Categoria nível 4 |
| Match_Type | Único, Ambíguo ou Nenhum |
| Matched_Terms | Termos que causaram o match |
| Match_Score | Score de confiança (0-1) |
| Classification_Source | "ML" ou "Dictionary" |
| Needs_Review | true se Ambíguo ou Nenhum |

### Errors
| Status | Descrição |
|--------|-----------|
| 400 | Parâmetro obrigatório ausente |
| 400 | Setor não encontrado na CONFIG |
| 500 | Erro ao ler arquivo |

---

## 3. TrainModel

**POST** `/TrainModel`

Treina um novo modelo ML para um setor específico.

### Request Body
```json
{
  "fileContent": "<base64-encoded-training-file>",
  "sector": "Varejo",
  "filename": "training_data.csv"
}
```

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| fileContent | string | ✅ | Arquivo com classificações (base64) |
| sector | string | ✅ | Setor do modelo |
| filename | string | ❌ | Nome para histórico |

### Colunas Esperadas no Arquivo
- `Descrição` (ou `DESCRICAO`, `Item_Description`)
- `N4` (ground truth)

### Response
```json
{
  "status": "success",
  "message": "Model trained successfully",
  "rawFileContent": "<base64-raw-file>",
  "rawFilename": "raw_training_data_varejo.xlsx",
  "report": "Training report...",
  "metrics": {
    "accuracy": 0.85,
    "f1_macro": 0.78
  }
}
```

### Errors
| Status | Descrição |
|--------|-----------|
| 400 | Colunas obrigatórias ausentes |
| 400 | Dados insuficientes (< 10 registros) |

---

## 4. GetModelHistory

**GET** `/GetModelHistory?sector={sector}`

Retorna histórico de versões de modelo para um setor.

### Query Parameters
| Param | Tipo | Descrição |
|-------|------|-----------|
| sector | string | Nome do setor |

### Response
```json
[
  {
    "version_id": "v_3",
    "timestamp": "2025-12-13T10:30:00",
    "filename": "dataset.csv",
    "metrics": {
      "accuracy": 0.85,
      "f1_macro": 0.78,
      "total_samples": 5000
    },
    "status": "active"
  },
  {
    "version_id": "v_2",
    "timestamp": "2025-12-12T15:00:00",
    "filename": "old_data.csv",
    "metrics": {
      "accuracy": 0.80,
      "f1_macro": 0.72,
      "total_samples": 3000
    },
    "status": "inactive"
  }
]
```

---

## 5. SetActiveModel

**POST** `/SetActiveModel`

Faz rollback para uma versão anterior do modelo.

### Request Body
```json
{
  "sector": "varejo",
  "version_id": "v_2"
}
```

### Response
```json
{
  "message": "Successfully rolled back to v_2"
}
```

### Errors
| Status | Descrição |
|--------|-----------|
| 400 | Setor ou version_id ausente |
| 404 | Versão não encontrada |

---

## Formatos de Arquivo Suportados

### Input (fileContent)
- Excel: `.xlsx`, `.xls`
- CSV: `;` ou `,` como delimitador
- Encoding: UTF-8

### Output (fileContent)
- Excel: `.xlsx` (OpenPyXL)
- 2 sheets: `Classificação` e `Analytics`

---

## Analytics Retornados

### Pareto (por nível N1-N4)
```json
{
  "N4": "Café",
  "Contagem": 150,
  "% do Total": 0.15,
  "% Acumulado": 0.15,
  "Classe": "A"
}
```

### Gaps
```json
{
  "Palavra": "servico",
  "Frequencia": 45
}
```

### Ambiguity
```json
{
  "Combinacao_N4": "Café | Chá",
  "Contagem": 12
}
```

---

## 6. GetModelInfo

**GET** `/GetModelInfo?sector={sector}&version_id={version_id}`

Retorna informações detalhadas sobre uma versão do modelo.

### Query Parameters
| Param | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| sector | string | ✅ | Nome do setor |
| version_id | string | ❌ | ID da versão (default: versão ativa) |

### Response
```json
{
  "sector": "varejo",
  "version_id": "v_1",
  "hierarchy": {
    "N1_count": 10,
    "N2_count": 45,
    "N3_count": 120,
    "N4_count": 350,
    "tree": {...}
  },
  "training_stats": {
    "total_descriptions": 34000,
    "by_n4": [{"N4": "Café", "count": 150}, ...]
  },
  "metrics": {
    "accuracy": 0.89,
    "f1_macro": 0.80,
    "total_samples": 34000
  },
  "comparison": {
    "previous_version": "v_0",
    "metrics": {...}
  }
}
```

---

## 7. GetTrainingData

**GET** `/GetTrainingData?sector={sector}&page={page}&page_size={page_size}`

Retorna dados de treinamento do `dataset_master.csv` com paginação.

### Query Parameters
| Param | Tipo | Default | Descrição |
|-------|------|---------|-----------|
| sector | string | - | Nome do setor (obrigatório) |
| page | int | 1 | Página atual |
| page_size | int | 50 | Items por página (max: 200) |
| version | string | - | Filtrar por versão |
| n4 | string | - | Filtrar por categoria N4 |
| search | string | - | Busca na descrição |

### Response
```json
{
  "data": [
    {
      "row_id": 0,
      "Descrição": "Café Torrado Premium",
      "N1": "Alimentício",
      "N2": "Bebidas",
      "N3": "Café",
      "N4": "Café em Grãos",
      "added_version": "v_1",
      "Ocorrências": 15
    }
  ],
  "total": 9600,
  "total_with_duplicates": 34000,
  "page": 1,
  "page_size": 50,
  "total_pages": 192,
  "versions": ["v_1", "v_2"]
}
```

> **Nota**: Os dados são agrupados por (Descrição, N4, Versão). A coluna `Ocorrências` mostra quantas duplicatas existem no dataset real.

---

## 8. DeleteTrainingData

**POST** `/DeleteTrainingData`

Remove dados de treinamento do `dataset_master.csv`.

### Request Body
```json
{
  "sector": "varejo",
  "version": "v_2",
  "items": [
    {"descricao": "Café Torrado", "n4": "Café em Grãos", "version": "v_1"}
  ],
  "row_ids": [1, 2, 3]
}
```

| Campo | Tipo | Descrição |
|-------|------|-----------|
| sector | string | Setor (obrigatório) |
| version | string | Deletar toda uma versão |
| items | array | Lista de items específicos (deleta todas duplicatas) |
| row_ids | array | Índices de linha (legado) |

> **Prioridade**: `version` > `items` > `row_ids`

### Response
```json
{
  "message": "Deleted 150 rows",
  "remaining": 33850
}
```
