import json
import os
import requests
import logging

# Configure logging to console
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_settings():
    """Load settings manually from local.settings.json"""
    try:
        with open('local.settings.json', 'r') as f:
            data = json.load(f)
            return data.get('Values', {})
    except Exception as e:
        logging.error(f"Failed to load local.settings.json: {e}")
        return {}

def test_grok():
    print("--- INICIANDO TESTE DO GROK ---")
    
    settings = load_settings()
    api_key = settings.get("GROK_API_KEY")
    endpoint = settings.get("GROK_API_ENDPOINT", "https://api.x.ai/v1")
    model = settings.get("GROK_MODEL_NAME", "grok-4-1-fast-reasoning")
    
    # Clean endpoint format
    endpoint = f"{endpoint.rstrip('/')}/chat/completions"

    print(f"ENDPOINT: {endpoint}")
    print(f"MODELO: {model}")
    
    if not api_key:
        print("ERRO: GROK_API_KEY não encontrada no local.settings.json")
        return
        
    print(f"CHAVE (Final): ...{api_key[-5:] if len(api_key)>5 else 'CURTA'}")

    # Test Payload
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Você é um classificador útil. Responda apenas JSON."},
            {"role": "user", "content": "Classifique: Caneta Azul. Formato: {'item': 'Caneta', 'categoria': 'Material'}"}
        ],
        "temperature": 0.0
    }

    print("\nEnviando requisição...")
    
    try:
        response = requests.post(
            endpoint,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            },
            json=payload,
            timeout=30
        )
        
        print(f"\nSTATUS CODE: {response.status_code}")
        print(f"RESPOSTA RAW:\n{response.text}")
        
        if response.status_code == 200:
            print("\nSUCESSO! A conexão está funcionando.")
        else:
            print("\nFALHA! Verifique o erro acima.")
            
    except Exception as e:
        print(f"\nERRO DE CONEXÃO: {e}")

if __name__ == "__main__":
    test_grok()
