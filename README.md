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

## Limpeza

Para restaurar o modelo original após o demo, delete a versão criada na aba **Gerenciar Modelos**.
