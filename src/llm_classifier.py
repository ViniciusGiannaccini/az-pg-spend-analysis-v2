"""
LLM Classifier for Standard/UNSPSC Mode.
Uses Azure OpenAI to classify items when the ML model is uncertain or when "Padrão" mode is selected.
"""

import os
import json
import logging
import requests
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# UNSPSC Segment/Family definitions for prompt context
# We use a simplified subset to guide the model, or rely on its internal knowledge (GPT-4 handles UNSPSC well)
UNSPSC_CONTEXT = """
Classifique os itens abaixo na taxonomia UNSPSC (United Nations Standard Products and Services Code).
Retorne o Segmento (N1) e a Família (N2) mais adequados.
Exemplos:
- "Caneta Esferográfica" -> N1: "Material de Escritório", N2: "Instrumentos de Escrita"
- "Licença Microsoft Office" -> N1: "Software", N2: "Software de Negócios"
- "Serviço de Limpeza Predial" -> N1: "Serviços Prediais", N2: "Limpeza e Manutenção"
- "Consultoria Financeira" -> N1: "Serviços Financeiros", N2: "Consultoria"
"""

def get_azure_openai_config():
    """Retrieves Azure OpenAI config from environment variables."""
    return {
        "endpoint": os.getenv("GROK_API_ENDPOINT", "https://api.x.ai/v1"),
        "api_key": os.getenv("GROK_API_KEY", ""),
        "deployment": os.getenv("GROK_MODEL_NAME", "grok-beta")
    }

def classify_items_with_llm(
    descriptions: List[str], 
    sector: str = "Padrão", 
    client_context: str = "", 
    custom_hierarchy: Optional[Dict] = None
) -> List[Dict[str, str]]:
    """
    Classifies a list of item descriptions using Azure OpenAI.
    
    Args:
        descriptions: List of text descriptions to classify.
        sector: The industry sector to provide context (e.g. 'Varejo', 'Educacional').
        client_context: Additional context about the client/project (e.g. 'Dengo - Chocolate').
        custom_hierarchy: Optional dictionary containing the allowed categories (N1-N4).
        
    Returns:
        List of dicts with keys: N1, N2, N3, N4, confidence, explanation
    """
    config = get_azure_openai_config()
    
    # Validation
    if not config["endpoint"] or not config["api_key"] or config["api_key"] == "SUA-CHAVE-AQUI":
        logging.warning("Azure OpenAI keys not configured. Skipping LLM classification.")
        return [_create_empty_result() for _ in descriptions]

    # Prepare batch prompt (process in chunks if needed, here we assume small batches or separate calls)
    # For a list, we might want to process all at once if small, or loop.
    # To keep response structured, we'll ask for JSON.
    
    results = [None] * len(descriptions)
    
    # Process in larger batches (50 items) and use parallel threads
    chunk_size = 50
    chunks = []
    for i in range(0, len(descriptions), chunk_size):
        chunks.append((i, descriptions[i:i + chunk_size]))
    
    logging.info(f"Starting parallel LLM classification with {len(chunks)} chunks...")
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_chunk = {
            executor.submit(_call_openai_api, chunk_items, config, sector, client_context, custom_hierarchy): chunk_start 
            for chunk_start, chunk_items in chunks
        }
        
        for future in as_completed(future_to_chunk):
            chunk_start = future_to_chunk[future]
            try:
                chunk_results = future.result()
                # Place results back in correct order
                for offset, res in enumerate(chunk_results):
                    if chunk_start + offset < len(results):
                        results[chunk_start + offset] = res
            except Exception as e:
                logging.error(f"Chunk starting at {chunk_start} failed: {e}")
                # Fallback for the whole chunk if it failed
                num_items = len(chunks[0][1]) if chunks else 1
                for offset in range(num_items):
                    idx = chunk_start + offset
                    if idx < len(results):
                        results[idx] = _create_manual_fallback("Erro no processamento paralelo")
        
    return [r if r is not None else _create_manual_fallback("Falha no mapeamento") for r in results]

def _create_empty_result():
    return {
        "N1": "", "N2": "", "N3": "", "N4": "",
        "LLM_Explanation": "LLM não configurado",
        "confidence": 0.0
    }

def _call_openai_api(
    items: List[str], 
    config: Dict, 
    sector: str = "Padrão", 
    client_context: str = "", 
    custom_hierarchy: Optional[Dict] = None
) -> List[Dict]:
    """Helper to call the API for a chunk of items."""
    
    # Construct the system message
    client_info = f"para o cliente: {client_context}" if client_context else ""
    
    # Construct the system message using the User's specific "Consultant" persona
    client_name = client_context if client_context else "ACNE" # Default placeholder if not provided
    
    system_message = (
        f"Você é um especialista em categorização de spend corporativo, com experiência em estruturas de classificação como UNSPSC e em modelos customizados de categorias de Compras. "
        f"Sua tarefa é categorizar automaticamente cada item da base de gastos segundo o Contexto/Cliente: '{client_name}'. "
        "ATENÇÃO: Se o contexto acima contiver 'Regras' ou instruções específicas, aplique-as com prioridade máxima sobre seu conhecimento geral.\n"
        "utilizando uma árvore de categorias que está disponibilizada abaixo. "
        "Caso fique em dúvida na classificação ou não conseguiu identificar na árvore, coloque 'Não Identificado' em todos os níveis (N1-N4). "
        "Os dados serão processados para Excel, então avalie item por linha.\n\n"
        
        "REGRAS DE OURO PARA RACIOCÍNIO:\n"
        "Preste extrema atenção na descrição do item, pois palavras-chave mudam radicalmente a categoria.\n"
        "Exemplo Clássico do 'Tubo':\n"
        "- Se 'Tubo' contiver 'PVC' -> MRO > Materiais de Construção > Produtos Sanitários e Hidráulicos\n"
        "- Se 'Tubo' contiver 'AÇO' ou 'CARBONO' -> Industrial > Materiais Industriais > Tubulações Industriais\n\n"
        
        "Analise cada palavra antes de decidir. Use a lógica do modelo 'grok-4-1-fast-reasoning' para desambiguar contextos.\n"
        "IMPORTANTE: Retorne a resposta APENAS no formato JSON abaixo (array de objetos), sem markdown. "
        "Exemplo de Saída:\n"
        '[{"item": "Tubo PVC 10mm", "N1": "MRO", "N2": "Materiais de Construção", "N3": "Produtos Sanitários", "N4": "Tubos", "confidence": 0.95}, ...]'
    )
    
    # If hierarchy is present, append it to user message or system message
    hierarchy_context = ""
    if custom_hierarchy:
        # Just a small snippet or mention of hierarchy for the prompt
        # In a real scenario, we might want to send the whole tree if it fits, or a summary
        # For this implementation, we'll assume the hierarchy is passed as a reference
        hierarchy_context = "\nUse a seguinte hierarquia como base:\n" + json.dumps(custom_hierarchy, ensure_ascii=False) # Full hierarchy passed
    
    user_content = f"Classifique os seguintes itens{hierarchy_context}:\n" + "\n".join([f"- {item}" for item in items])

    payload = {
        "model": config["deployment"],
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_content}
        ],
        "temperature": 0.0,
    }

    # xAI (Grok) API endpoint
    endpoint = f"{config['endpoint'].rstrip('/')}/chat/completions"
    
    # DEBUG: Validating configuration
    if not config["api_key"] or len(config["api_key"]) < 10:
        logging.warning("CRITICAL: Grok API Key missing or too short!")

    try:
        logging.info(f"Sending request to Grok with input size {len(items)}")
        response = requests.post(
            endpoint,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {config['api_key']}"
            },
            json=payload,
            timeout=60
        )
        
        if response.status_code != 200:
            logging.error(f"Grok API Error {response.status_code}: {response.text}")
            return [_create_manual_fallback(item) for item in items]
            
        data = response.json()
        content = data['choices'][0]['message']['content']
        
        # LOG RAW CONTENT FOR DEBUGGING (Info level to keep it visible but correct)
        logging.info(f"RAW LLM RESPONSE: {content[:200]}...") 

        # Clean Markdown code blocks if present
        if "```" in content:
            content = content.replace("```json", "").replace("```", "").strip()

        # Parse JSON output
        parsed = json.loads(content)
        
        # Check for error responses from Azure OpenAI
        if isinstance(parsed, dict) and "error" in parsed:
            error_msg = parsed.get("error", "Unknown error")
            logging.error(f"Azure OpenAI returned error: {error_msg}")
            return [_create_manual_fallback(item, f"API Error: {error_msg}") for item in items]
        
        # Handle different response formats:
        # 1. Direct dict with N1-N4 keys (single item)
        # 2. Dict with a list value (batch with wrapper key)
        # 3. Direct list (batch without wrapper)
        
        if isinstance(parsed, dict):
            # Check if it's a single-item response with N1-N4 keys
            if "N1" in parsed or "N2" in parsed:
                # Single item response - wrap in list
                parsed = [parsed]
            else:
                # Try to find a list value in the dict (e.g., {"items": [...]})
                for key, val in parsed.items():
                    if isinstance(val, list):
                        parsed = val
                        break
                else:
                    # No list found and no N1-N4 keys - unexpected format
                    logging.warning(f"LLM returned unexpected dict format: {list(parsed.keys())}")
                    return [_create_manual_fallback(item, "Formato inesperado") for item in items]
        
        if not isinstance(parsed, list):
            logging.warning("LLM returned unexpected format (not list after processing)")
            return [_create_manual_fallback(item, "Formato inesperado") for item in items]
            
        # Map back to results
        formatted_results = []
        
        # For batch processing, try to match results to input items
        for idx, item_text in enumerate(items):
            match = None
            
            # Try multiple matching strategies:
            # 1. Match by index (if LLM preserved order)
            if idx < len(parsed):
                candidate = parsed[idx]
                if candidate.get("N1") or candidate.get("N2"):
                    match = candidate
            
            # 2. Match by item text in response
            if not match:
                match = next((r for r in parsed if r.get('item') == item_text or item_text in str(r.get('item', ''))), None)
            
            # 3. Use first unmatched result (fallback)
            if not match and len(parsed) > 0:
                match = parsed[0]
                parsed = parsed[1:]  # Remove used result
            
            if match and (match.get("N1") or match.get("N2")):
                formatted_results.append({
                    "N1": match.get("N1", ""),
                    "N2": match.get("N2", ""),
                    "N3": match.get("N3", ""),
                    "N4": match.get("N4", ""),
                    "LLM_Explanation": "Classificado via Azure OpenAI (UNSPSC)",
                    "confidence": match.get("confidence", 0.8)
                })
            else:
                formatted_results.append(_create_manual_fallback(item_text, "Item não retornado pelo LLM"))
                
        return formatted_results

    except Exception as e:
        logging.error(f"Exception calling Azure OpenAI: {e}")
        return [_create_manual_fallback(item) for item in items]

def _create_manual_fallback(item_text, reason="Erro na API"):
    return {
        "N1": "", "N2": "", "N3": "", "N4": "",
        "LLM_Explanation": reason,
        "confidence": 0.0
    }
