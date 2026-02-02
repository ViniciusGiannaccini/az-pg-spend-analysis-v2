import requests
import base64
import pandas as pd
import io
import json

# Create dummy Excel
df = pd.DataFrame({
    "Descrição": ["Teste Tubo Inox", "Teste Caneta Azul"],
    "N1": ["Industrial", "Material Escritorio"],
    "N2": ["Tubulações", "Escrita"],
    "N3": ["Aço", "Esferográfica"],
    "N4": ["Tubo Inox", "Caneta"]
})

# Save to bytes
output = io.BytesIO()
with pd.ExcelWriter(output, engine='openpyxl') as writer:
    df.to_excel(writer, index=False)
excel_data = output.getvalue()

# Encode Base64
b64_data = base64.b64encode(excel_data).decode('utf-8')

# Payload
payload = {
    "fileContent": b64_data,
    "sector": "Padrão",
    "filename": "test_memory.xlsx"
}

# Send Request
url = "http://localhost:7071/api/TrainModel"
print(f"Sending request to {url}...")

try:
    response = requests.post(url, json=payload)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
