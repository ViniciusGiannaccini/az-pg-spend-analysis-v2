# Cenário de Demonstração - Empresa X (Educacional)

## Objetivo

Demonstrar como o treinamento do modelo ML melhora a taxa de classificação única.

## Arquivos

| Arquivo | Descrição | Linhas |
|---------|-----------|--------|
| `demo_empresa_x_para_classificar.xlsx` | Arquivo para classificar (SKU + Descrição) | 200 |
| `demo_treino_empresa_x.xlsx` | Arquivo de treino (Descrição + N1/N2/N3/N4) | ~1500 |

## Fluxo do Demo

### Passo 1: Classificar SEM treino adicional

1. Acesse a aplicação
2. Na aba **Classificar Itens**, selecione setor **Educacional**
3. Faça upload do arquivo `demo_empresa_x_para_classificar.xlsx`
4. **Resultado esperado**: Taxa de únicos baixa (~5%)

### Passo 2: Treinar modelo

1. Vá para a aba **Treinar Modelo**
2. Selecione setor **Educacional**
3. Faça upload do arquivo `demo_treino_empresa_x.xlsx`
4. Aguarde o treinamento completar
5. **Reinicie o servidor** (`func start`) para carregar novo modelo

### Passo 3: Classificar APÓS treino

1. Na aba **Classificar Itens**, selecione setor **Educacional**
2. Faça upload do mesmo arquivo `demo_empresa_x_para_classificar.xlsx`
3. **Resultado esperado**: Taxa de únicos significativamente maior

## Categorias no Cenário

O arquivo de treino cobre 8 categorias N4:

- Frutas | Coffe | Desjejum
- Papelaria Administrativa  
- Suprimento Didatico
- Materiais Limpeza | Higiene
- Outros Equipamentos T.I
- Outros Materiais Eletricos
- Restaurante | Copa | Cozinha
- Acessorios Mobiliario

## Importante

> ⚠️ **O servidor precisa ser reiniciado após o treinamento** para carregar o novo modelo ML. Isso é porque o modelo é cacheado em memória.


## Rodando Localmente

### Backend (Azure Functions)
1. Instale o [Azure Functions Core Tools](https://learn.microsoft.com/en-us/azure/azure-functions/functions-run-local).
2. Vá para a pasta raiz `az-pg-spend-analysis`.
3. Crie um arquivo `local.settings.json` com suas credenciais.
4. Inicie o servidor:
   ```bash
   func start
   ```

### Frontend (Next.js)
1. Vá para a pasta `frontend`.
2. Instale as dependências: `npm install`.
3. Crie um arquivo `.env.local` e configure:
   ```
   NEXT_PUBLIC_API_URL=http://localhost:7071/api
   NEXT_PUBLIC_FUNCTION_KEY= (vazio localmente)
   ```
4. Inicie o servidor:
   ```bash
   npm run dev
   ```

## Deploy

### 1. Backend (Azure Functions)
**Importante**: As rotas agora são `AuthLevel.ANONYMOUS` para permitir CORS sem problemas. A segurança deve ser gerenciada via configurações de rede da Azure ou API Gateway se necessário.

1. Login na Azure: `az login`
2. Deploy via CLI:
   ```bash
   func azure functionapp publish <NOME_DA_SUA_FUNCTION_APP>
   ```
   *Nota: O arquivo `.funcignore` já está configurado para incluir a pasta `models` e excluir dados de treinamento brutos.*

### 2. Frontend (Vercel)
1. Instale a Vercel CLI: `npm i -g vercel`
2. Na pasta raiz, rode: `vercel`
3. Configure as variáveis de ambiente na Vercel:
   - `NEXT_PUBLIC_API_URL`: URL da sua Azure Function (ex: `https://sua-function.azurewebsites.net/api`)
   - `NEXT_PUBLIC_FUNCTION_KEY`: Sua System Key da Azure Function (embora as rotas sejam anônimas, o front ainda envia o header).

## Limpeza

Para restaurar o modelo original após o demo, delete a versão criada na aba **Gerenciar Modelos**.
