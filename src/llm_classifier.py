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
        "endpoint": os.getenv("AZURE_OPENAI_ENDPOINT", ""),
        "api_key": os.getenv("AZURE_OPENAI_KEY", ""),
        "deployment": os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o")
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
    
    system_message = (
        f"Você é um especialista em classificação de gastos (Spend Analysis) {client_info}. "
        f"Considere que estamos operando no setor: {sector}. "
    )

    if custom_hierarchy:
        # Grounding with custom hierarchy
        system_message += (
            "Sua tarefa é classificar materiais e serviços utilizando como base a hierarquia customizada fornecida. "
            "Tente manter-se fiel às categorias (N1, N2, N3, N4) da hierarquia fornecida. "
            "Se um item não se encaixar perfeitamente em nenhuma categoria, escolha a categoria mais genérica ou próxima disponível na hierarquia. "
            "IMPORTANTE: Você deve SEMPRE retornar a resposta no formato JSON solicitado, nunca responda com mensagens de erro ou justificativas de que não conseguiu classificar."
        )
    else:
        # Default to UNSPSC
        system_message += (
            "Sua tarefa é classificar materiais e serviços usando a taxonomia UNSPSC. "
            "Considere o contexto do setor para decidir a categoria mais adequada (ex: Ar Condicionado em Escola pode ser Infraestrutura Escolar, em Indústria pode ser Facilities/MRO). "
        )

    system_message += (
        "Para cada item, identifique o Segmento (N1), Família (N2), Classe (N3) e Mercadoria (N4). "
        "Responda APENAS um array JSON. Exemplo: "
        '[{"item": "Caneta", "N1": "Material de Escritório", "N2": "Escrita", "N3": "Canetas", "N4": "Caneta Esferográfica", "confidence": 0.95}]'
    )
    
    # If hierarchy is present, append it to user message or system message
    hierarchy_context = ""
    if custom_hierarchy:
        # Just a small snippet or mention of hierarchy for the prompt
        # In a real scenario, we might want to send the whole tree if it fits, or a summary
        # For this implementation, we'll assume the hierarchy is passed as a reference
        hierarchy_context = "\nUse a seguinte hierarquia como base:\n" + json.dumps(custom_hierarchy, ensure_ascii=False)[:3000] # Limit to avoid huge prompts
    
    user_content = f"Classifique os seguintes itens{hierarchy_context}:\n" + "\n".join([f"- {item}" for item in items])

    payload = {
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_content}
        ],
        "temperature": 0.0,
        "response_format": { "type": "json_object" } # Force JSON if supported by model (gpt-4o supports it)
    }

    endpoint = f"{config['endpoint'].rstrip('/')}/openai/deployments/{config['deployment']}/chat/completions?api-version=2024-02-15-preview"
    
    try:
        response = requests.post(
            endpoint,
            headers={
                "Content-Type": "application/json",
                "api-key": config["api_key"]
            },
            json=payload,
            timeout=60
        )
        
        if response.status_code != 200:
            logging.error(f"Azure OpenAI Error {response.status_code}: {response.text}")
            return [_create_manual_fallback(item) for item in items]
            
        data = response.json()
        content = data['choices'][0]['message']['content']
        
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
