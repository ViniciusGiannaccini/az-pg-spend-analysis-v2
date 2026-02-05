"""
Azure Function for Spend Analysis Classification.

This module provides an HTTP endpoint to process Excel files containing item descriptions.
It supports both dictionary-based and ML-enhanced hybrid classification.
"""

import logging
import json
import io
import csv
import base64
import os
import shutil
from datetime import datetime, timedelta
import uuid
import requests

# Power Automate Flow URL for saving classified files to SharePoint
POWER_AUTOMATE_URL = os.getenv("POWER_AUTOMATE_URL", "")
POWER_AUTOMATE_API_KEY = os.getenv("POWER_AUTOMATE_API_KEY", "")

# Models directory: Use /home/models in Azure (writable), ./models locally
# Azure Functions has read-only /home/site/wwwroot, but /home is writable and persistent
def get_models_dir() -> str:
    """Get the appropriate models directory based on environment."""
    # Check if running in Azure (WEBSITE_INSTANCE_ID is set in Azure App Service/Functions)
    if os.getenv("WEBSITE_INSTANCE_ID") or os.getenv("AZURE_FUNCTIONS_ENVIRONMENT"):
        azure_models = "/home/models"
        try:
            os.makedirs(azure_models, exist_ok=True)
            
            # BOOTSTRAP: Initialize models from read-only package to writable /home
            # Package location behavior: /home/site/wwwroot/models
            package_models = os.path.join(os.getcwd(), "models") 
            # Note: os.getcwd() usually returns /home/site/wwwroot in Azure Functions
            
            # Copy only if destination is empty (first run) or if we want to force update (logic can be refined)
            # For now: Initialize if empty to ensure writable access
            if os.path.exists(package_models) and not os.listdir(azure_models):
                logging.info(f"[BOOTSTRAP] Initializing models from {package_models} to {azure_models}...")
                shutil.copytree(package_models, azure_models, dirs_exist_ok=True)
                logging.info("[BOOTSTRAP] Models copied successfully.")
            elif not os.path.exists(package_models):
                 logging.warning(f"[BOOTSTRAP] Source models not found at {package_models}. Starting empty.")

        except Exception as e:
            logging.error(f"[BOOTSTRAP] Error initializing models directory: {e}")
            # Fallback to local if copy fails (though likely won't work well in Azure if read-only)
            pass  
        return azure_models
    # Local development
    return "models"

MODELS_DIR = get_models_dir()


def send_to_power_automate(filename: str, file_content_base64: str) -> bool:
    """
    Send classified file to Power Automate Flow for saving to SharePoint.
    
    Args:
        filename: Name of the classified file
        file_content_base64: Base64 encoded content of the Excel file
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not POWER_AUTOMATE_URL:
        logging.warning("POWER_AUTOMATE_URL not configured. Skipping SharePoint log.")
        return False
    
    try:
        payload = {
            "filename": filename,
            "fileContent": file_content_base64
        }
        
        response = requests.post(
            POWER_AUTOMATE_URL,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "api-key": POWER_AUTOMATE_API_KEY
            },
            timeout=30
        )
        
        if response.status_code in [200, 202]:
            logging.info(f"Successfully sent file '{filename}' to Power Automate for SharePoint logging.")
            return True
        else:
            logging.warning(f"Power Automate returned status {response.status_code}: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        logging.warning(f"Timeout sending file to Power Automate. File: {filename}")
        return False
    except requests.exceptions.RequestException as e:
        logging.warning(f"Error sending file to Power Automate: {e}")
        return False

def safe_json_dumps(obj):
    """
    Safely serialize object to JSON, replacing NaN/Inf with None (null).
    """
    import json
    import math
    
    def clean_obj(inner_obj):
        if isinstance(inner_obj, dict):
            return {k: clean_obj(v) for k, v in inner_obj.items()}
        elif isinstance(inner_obj, list):
            return [clean_obj(i) for i in inner_obj]
        elif isinstance(inner_obj, float):
            if math.isnan(inner_obj) or math.isinf(inner_obj):
                return None
        return inner_obj
        
    return json.dumps(clean_obj(obj), ensure_ascii=False)


import azure.functions as func
app = func.FunctionApp()


@app.route(
    route="get-token",
    methods=["GET", "OPTIONS"],
    auth_level=func.AuthLevel.ANONYMOUS
)
def GetDirectLineToken(req: func.HttpRequest) -> func.HttpResponse:
    """
    Generate a temporary Direct Line token for the frontend to use.
    
    This endpoint exchanges the Direct Line secret (stored securely in environment variables)
    for a temporary token that the frontend can safely use to connect to the bot.
    
    Security: The secret never leaves the backend, and tokens expire after 30 minutes.
    
    Returns:
        func.HttpResponse: JSON containing the token and conversationId
    """
    # Handle CORS preflight (OPTIONS) request
    if req.method == "OPTIONS":
        return func.HttpResponse(
            status_code=200,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            }
        )
    
    logging.info('GetDirectLineToken HTTP trigger function processed a request.')
    
    # Get Direct Line secret from environment variable
    direct_line_secret = os.getenv("DIRECT_LINE_SECRET")
    
    if not direct_line_secret:
        logging.error("DIRECT_LINE_SECRET environment variable not configured")
        return func.HttpResponse(
            body=safe_json_dumps({"error": "Direct Line not configured"}),
            status_code=500,
            mimetype="application/json",
        )
    
    try:
        # Call Direct Line API to start a new conversation
        response = requests.post(
            "https://directline.botframework.com/v3/directline/conversations",
            headers={
                "Authorization": f"Bearer {direct_line_secret}",
                "Content-Type": "application/json"
            },
            timeout=10
        )
        
        if response.status_code in [200, 201]:
            conversation_data = response.json()
            logging.info(f"Direct Line conversation created: {conversation_data.get('conversationId')}")
            
            # Enable CORS for the frontend
            headers = {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            }
            
            return func.HttpResponse(
                body=safe_json_dumps(conversation_data),
                status_code=200,
                mimetype="application/json",
                headers=headers
            )
        else:
            logging.error(f"Direct Line API error: {response.status_code} - {response.text}")
            return func.HttpResponse(
                safe_json_dumps({"error": "Failed to create conversation"}),
                status_code=response.status_code,
                mimetype="application/json"
            )
            
    except requests.exceptions.RequestException as e:
        logging.error(f"Request to Direct Line API failed: {e}")
        return func.HttpResponse(
            safe_json_dumps({"error": "Network error contacting Direct Line"}),
            status_code=500,
            mimetype="application/json"
        )
    except Exception as e:
        logging.error(f"Unexpected error in get_direct_line_token: {e}")
        return func.HttpResponse(
            safe_json_dumps({"error": "Internal server error"}),
            status_code=500,
            mimetype="application/json"
        )


@app.route(
    route="ProcessTaxonomy",
    methods=["POST", "OPTIONS"],
    auth_level=func.AuthLevel.ANONYMOUS
)
def ProcessTaxonomy(req: func.HttpRequest) -> func.HttpResponse:
    import pandas as pd
    from src.taxonomy_mapper import load_custom_hierarchy, apply_custom_hierarchy
    from src.taxonomy_engine import COL_DESC_CANDIDATES_DEFAULT
    USE_ML_CLASSIFIER = os.getenv("USE_ML_CLASSIFIER", "false").lower() == "true"
    GROK_API_KEY = os.getenv("GROK_API_KEY")
    # Enable LLM if key is present and not the placeholder
    USE_LLM = bool(GROK_API_KEY and "SUA-CHAVE" not in GROK_API_KEY)
    """
    Process an uploaded Excel file and perform taxonomy classification based on a provided dictionary.

    The request body must be a JSON object containing:
    - fileContent: Base64 encoded string of the items Excel file.
    - dictionaryContent: Base64 encoded string of the dictionary XLSX file.
    - sector: Sector name to determine which dictionary sheet to use (e.g., 'Varejo').
    - originalFilename: (Optional) The name of the original file.

    Returns:
        func.HttpResponse: A JSON response containing the base64 encoded result Excel,
                           a summary of the taxonomy, and status information.
    """
    # Handle CORS preflight (OPTIONS) request
    if req.method == "OPTIONS":
        return func.HttpResponse(
            status_code=200,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            }
        )
    
    logging.info('ProcessTaxonomy HTTP trigger function processed a request.')
    
    # Generate unique session ID for this analysis
    session_id = str(uuid.uuid4())

    try:
        req_body = req.get_json()
        logging.info("Request body received.")
    except ValueError:
        req_body = {}

    file_content_b64 = req_body.get("fileContent")
    dict_content_b64 = req_body.get("dictionaryContent")
    sector = req_body.get("sector")
    original_filename = req_body.get("originalFilename", "")
    custom_hierarchy_b64 = req_body.get("customHierarchy")
    client_context = req_body.get("clientContext", "")

    # Defensive check: sometimes frontend might send strings "undefined" or "null" instead of actual nulls/empty
    if dict_content_b64 in ["undefined", "null", "None"]: dict_content_b64 = None
    if custom_hierarchy_b64 in ["undefined", "null", "None"]: custom_hierarchy_b64 = None

    if not file_content_b64:
        logging.error("Missing fileContent in request.")
        return func.HttpResponse(
            safe_json_dumps({"error": "Parâmetro 'fileContent' (base64) é obrigatório."}),
            status_code=400,
            mimetype="application/json"
        )

    if not dict_content_b64 and not custom_hierarchy_b64:
        logging.error("Missing both dictionaryContent and customHierarchy.")
        return func.HttpResponse(
            safe_json_dumps({"error": "É necessário fornecer um Dicionário ou uma Hierarquia Customizada."}),
            status_code=400,
            mimetype="application/json"
        )
    
    if not sector:
        return func.HttpResponse(
            "Parâmetro 'sector' é obrigatório no corpo da requisição.",
            status_code=400
        )
    
    # Normalize sector to title case (e.g., "varejo" -> "Varejo", "VAREJO" -> "Varejo")
    sector = sector.strip().capitalize()
    
    logging.info(f"Original filename received: {original_filename}")

    try:
        file_bytes = base64.b64decode(file_content_b64)
    except Exception as e:
        logging.error(f"Error decoding base64 fileContent: {e}")
        return func.HttpResponse(
            "Parameter 'fileContent' (base64) decoding error.",
            status_code=400
        )

    try:
        dict_bytes = base64.b64decode(dict_content_b64)
    except Exception as e:
        logging.error(f"Error decoding base64 dictionaryContent: {e}")
        return func.HttpResponse(
            "Parameter 'dictionaryContent' (base64) decoding error.",
            status_code=400
        )

    # Load items file first as it's mandatory
    try:
        df_items = pd.read_excel(io.BytesIO(file_bytes))
        logging.info("Successfully parsed items file as Excel")
    except Exception as e:
        logging.warning(f"Excel parsing failed for items, trying CSV: {e}")
        try:
            df_items = pd.read_csv(io.BytesIO(file_bytes), sep=';', encoding='utf-8', on_bad_lines='skip')
            logging.info("Successfully parsed items as CSV (semicolon)")
        except Exception:
            try:
                df_items = pd.read_csv(io.BytesIO(file_bytes), sep=',', encoding='utf-8', on_bad_lines='skip')
                logging.info("Successfully parsed items as CSV (comma)")
            except Exception as e3:
                return func.HttpResponse(f"Error reading items file: {str(e3)}", status_code=400)

    # Dictionary is optional if customHierarchy is provided (Exclusive Mode)
    df_dict = pd.DataFrame()
    if dict_content_b64:
        try:
            dict_bytes = base64.b64decode(dict_content_b64)
            # Parse dictionary CONFIG sheet
            df_config = pd.read_excel(io.BytesIO(dict_bytes), sheet_name='CONFIG')
            
            # Lookup sector
            df_config_valid = df_config.dropna(subset=['Setor'])
            sector_row = df_config_valid[df_config_valid['Setor'].str.strip().str.lower() == sector.strip().lower()]
            
            if sector_row.empty and sector.lower() != "padrão":
                available = df_config_valid['Setor'].dropna().unique().tolist()
                return func.HttpResponse(f"Setor '{sector}' não encontrado. Disponíveis: {', '.join(available)}", status_code=400)
            
            if not sector_row.empty:
                dict_sheet_name = sector_row.iloc[0]['ABA_DICIONARIO']
                df_dict = pd.read_excel(io.BytesIO(dict_bytes), sheet_name=dict_sheet_name)
                logging.info(f"Loaded dictionary '{dict_sheet_name}': {len(df_dict)} rows")
            else:
                logging.info(f"Sector '{sector}' not in dictionary. Proceeding in LLM-Only/Exclusive mode.")
        except Exception as e:
            logging.error(f"Error loading dictionary: {e}")
            if not custom_hierarchy_b64:
                return func.HttpResponse(f"Erro ao carregar dicionário: {str(e)}", status_code=400)
    else:
        logging.info("Activating Exclusive Mode (No default dictionary provided).")

    logging.info(f"Items file OK: {len(df_items)} rows, {len(df_items.columns)} columns")
    logging.info(f"Dictionary OK: {len(df_dict)} rows, {len(df_dict.columns)} columns")

    # Validate columns and identify description column
    # We expect at least 2 valid columns (not Unnamed) to proceed with the heuristic
    valid_cols = [c for c in df_items.columns if not str(c).startswith("Unnamed")]

    if len(valid_cols) < 2:
        logging.error("Excel file does not have at least 2 useful columns.")
        return func.HttpResponse("Invalid Excel file.", status_code=400)

    # Heuristic: assume the second valid column is the description
    # This is based on the typical structure of the input files where the first column is an ID or Item Description
    desc_source_col = valid_cols[1]
    logging.info(f"Description column detected: {desc_source_col}")

    df_items["Item_Description"] = df_items[desc_source_col]

    dict_records = df_dict.to_dict(orient="records")
    # item_records = df_items.to_dict(orient="records") # REMOVED: Memory hog for 60k rows

    try:
        # Use ML-enhanced hybrid classifier if enabled
        if USE_ML_CLASSIFIER:
            logging.info(f"Using ML hybrid classifier for sector: {sector}")
            
            # Create wrapper to process items in batch using hybrid classifier
            logging.info("Importing taxonomy engine...")
            from src.taxonomy_engine import build_patterns, normalize_text, generate_analytics
            
            # Decide if we use LLM fallback
            # Logic: If sector is "Padrão", we force LLM usage (if configured). 
            # If sector is specific but we have LLM configured, we can use it as fallback.
            use_llm_fallback = USE_LLM
            if sector == "Padrão" and not USE_LLM:
                logging.warning("Sector is 'Padrão' but Azure OpenAI key is missing. Classification may fail.")
            
            # Build dictionary patterns only if provided and NOT in Padrão mode
            patterns_by_n4, terms_by_n4, taxonomy_by_n4 = None, None, None
            if dict_content_b64 and sector.lower() != "padrão":
                logging.info("Building dictionary patterns...")
                patterns_by_n4, terms_by_n4, taxonomy_by_n4 = build_patterns(df_dict)
            else:
                logging.info(f"Skipping dictionary patterns (Sector: {sector}).")
            
            # Load ML model
            model_sector = sector if sector else "Varejo"
            if custom_hierarchy_b64:
                logging.info(f"Exclusive Mode: Using ML model '{model_sector}' as semantic base for custom hierarchy.")
            else:
                logging.info(f"Standard Mode: Using hybrid classifier with sector: {model_sector}")
                if sector == "Padrão": 
                     logging.info("Using Standard Mode (UNSPSC) with LLM.")
            
            from src.ml_classifier import load_model
            from src.hybrid_classifier import classify_hybrid
            
            vectorizer, classifier, label_encoder, hierarchy = None, None, None, None
            
            # Only load ML model if NOT Padrão (or if you want to use a fallback like Varejo for Padrão, but Padrão implies UNSPSC/LLM)
            if model_sector != "Padrão":
                try:
                    vectorizer, classifier, label_encoder, hierarchy = load_model(sector=model_sector, models_dir=MODELS_DIR)
                except Exception as e:
                    logging.warning(f"Failed to load model for {model_sector}: {e}. Proceeding without ML.")
            else:
                 logging.info("Skipping ML model load for sector 'Padrão'. Relying on LLM.")
            
            # Load custom hierarchy if provided
            custom_hierarchy = None
            if custom_hierarchy_b64:
                try:
                    custom_hierarchy = load_custom_hierarchy(custom_hierarchy_b64)
                    logging.info(f"Loaded custom hierarchy with {len(custom_hierarchy)} N4 categories")
                except Exception as e:
                    logging.warning(f"Failed to load custom hierarchy: {e}. Using default hierarchy.")
            
            # Load description column
            desc_column = "Item_Description"
            df_items["_desc_original"] = df_items[desc_column].fillna("").astype(str)
            df_items["_desc_norm"] = df_items["_desc_original"].map(normalize_text).astype(str)
            
            # 1. OPTIMIZATION: Setup Cache for Hybrid Classification
            from functools import lru_cache
            from src.taxonomy_mapper import apply_custom_hierarchy

            @lru_cache(maxsize=10000)
            def classify_cached(desc, desc_norm):
                # Core classification (Dictionary + ML)
                return classify_hybrid(
                    description=desc,
                    sector=sector,
                    dict_patterns=patterns_by_n4,
                    dict_terms=terms_by_n4,
                    dict_taxonomy=taxonomy_by_n4,
                    desc_norm=desc_norm,
                    vectorizer=vectorizer,
                    classifier=classifier,
                    label_encoder=label_encoder,
                    hierarchy=hierarchy or custom_hierarchy, # Pass either ML hierarchy or Custom hierarchy
                    use_llm_fallback=use_llm_fallback,
                    client_context=client_context
                ).to_dict()
                
                # 2. OPTIMIZATION: Apply Custom Hierarchy inside the cache pass
                if custom_hierarchy:
                    top_candidates = result.get('top_candidates', [])
                    if not top_candidates and result.get('N4'):
                        top_candidates = [{'N4': result['N4']}]
                    
                    custom_res, matched_n4 = apply_custom_hierarchy(top_candidates, custom_hierarchy)
                    
                    if custom_res:
                        # Found a match in custom hierarchy - OVERRIDE results
                        result['N1'] = custom_res.get('N1', '')
                        result['N2'] = custom_res.get('N2', '')
                        result['N3'] = custom_res.get('N3', '')
                        result['N4'] = custom_res.get('N4', '')
                        # Maintain consistency in results
                        result['classification_source'] = f"Custom (via {result['classification_source']})"
                    else:
                        # No match found in custom hierarchy - Clear and mark as Nenhum (per requirement)
                        if result.get('status') == 'Único':
                            original_n4 = result.get('N4', '')
                            result['N1'] = ''
                            result['N2'] = ''
                            result['N3'] = ''
                            result['N4'] = ''
                            result['status'] = 'Nenhum'
                            if original_n4:
                                result['matched_terms'] = [f'Original: {original_n4}']
                
                return result

            # Process each item using the optimized cached function with periodic progress logging
            logging.info(f"Processing {len(df_items)} items with hybrid classifier (caching enabled)...")
            results = []
            total_items = len(df_items)
            col_orig_idx = df_items.columns.get_loc("_desc_original")
            col_norm_idx = df_items.columns.get_loc("_desc_norm")
            
            # OPTIMIZATION: If sector is "Padrão", use batch LLM classification directly
            if sector == "Padrão":
                logging.info(f"Padrão mode detected: Using batch parallel LLM classification for {total_items} items.")
                from src.llm_classifier import classify_items_with_llm
                from src.hybrid_classifier import ClassificationResult
                
                # Deduplication logic: Only send unique descriptions to LLM
                all_descriptions = df_items["_desc_original"].tolist()
                unique_descriptions = list(dict.fromkeys(all_descriptions)) # Preserves order
                
                logging.info(f"Deduplication: {len(unique_descriptions)} unique items found out of {total_items} total.")
                
                llm_unique_results = classify_items_with_llm(
                    unique_descriptions, 
                    sector=sector, 
                    client_context=client_context, 
                    custom_hierarchy=hierarchy or custom_hierarchy
                )
                
                # Map unique results back to original list
                # Create a map of {description: formatted_result}
                desc_to_res = {}
                for i, res in enumerate(llm_unique_results):
                    formatted = {
                        "N1": res.get("N1", "Não Identificado"),
                        "N2": res.get("N2", "Não Identificado"),
                        "N3": res.get("N3", "Não Identificado"),
                        "N4": res.get("N4", "Não Identificado"),
                        "status": "Único" if res.get("N1") and res.get("N1") != "Não Identificado" else "Nenhum",
                        "matched_terms": [],
                        "ml_confidence": res.get("confidence", 0.0),
                        "classification_source": "LLM (UNSPSC Batch Optimized)",
                        "ambiguous_options": []
                    }
                    desc_to_res[unique_descriptions[i]] = formatted
                
                # Fill results in the original order
                for desc in all_descriptions:
                    results.append(desc_to_res[desc])
                    
                logging.info(f"Batch LLM classification (optimized) completed for {total_items} items.")
            else:
                # Standard Loop for Retail/Dictionary-First modes (already fast)
                # First pass: Dictionary + ML ONLY (Local)
                logging.info("Starting First Pass: Local classification (ML + Dictionary)...")
                
                # We temporarily disable LLM fallback for the first pass to collect items that need it
                for i, row in enumerate(df_items.itertuples(index=False), 1):
                    desc_orig = str(row[col_orig_idx])
                    desc_norm = str(row[col_norm_idx])
                    
                    # Force use_llm_fallback to False for the loop to avoid sequential calls
                    result = classify_hybrid(
                        description=desc_orig,
                        sector=sector,
                        dict_patterns=patterns_by_n4,
                        dict_terms=terms_by_n4,
                        dict_taxonomy=taxonomy_by_n4,
                        desc_norm=desc_norm,
                        vectorizer=vectorizer,
                        classifier=classifier,
                        label_encoder=label_encoder,
                        hierarchy=hierarchy or custom_hierarchy,
                        use_llm_fallback=False, # DISABLED in first pass
                        client_context=client_context
                    ).to_dict()
                    
                    results.append(result)
                    
                    if i % 50 == 0 or i == total_items:
                        percentage = (i / total_items) * 100
                        logging.info(f"Local Progress: {i}/{total_items} items processed ({percentage:.1f}%)")

                # Second pass: Batch LLM for remaining "Nenhum" (if LLM is enabled)
                if USE_LLM:
                    unclassified_indices = [idx for idx, res in enumerate(results) if res['status'] == 'Nenhum']
                    
                    if unclassified_indices:
                        num_to_llm = len(unclassified_indices)
                        logging.info(f"Starting Second Pass: Sending {num_to_llm} unclassified items to LLM in batch...")
                        
                        from src.llm_classifier import classify_items_with_llm
                        unclassified_descs = [df_items.iloc[idx]["_desc_original"] for idx in unclassified_indices]
                        
                        llm_batch_results = classify_items_with_llm(
                            unclassified_descs,
                            sector=sector,
                            client_context=client_context,
                            custom_hierarchy=hierarchy or custom_hierarchy
                        )
                        
                        # Merge LLM results back into the results list
                        for i, res in enumerate(llm_batch_results):
                            if res.get("N1"): # If LLM found a match
                                target_idx = unclassified_indices[i]
                                results[target_idx].update({
                                    "N1": res.get("N1", ""),
                                    "N2": res.get("N2", ""),
                                    "N3": res.get("N3", ""),
                                    "N4": res.get("N4", ""),
                                    "status": "Único",
                                    "ml_confidence": res.get("confidence", 0.0),
                                    "classification_source": "LLM (UNSPSC Fallback Batch)"
                                })
                        logging.info(f"Second pass completed. {num_to_llm} items processed via LLM.")
                    else:
                        logging.info("All items classified locally. Skipping LLM pass.")
            
            # Convert results back to DataFrame columns
            df_items["N1"] = [r["N1"] for r in results]
            df_items["N2"] = [r["N2"] for r in results]
            df_items["N3"] = [r["N3"] for r in results]
            df_items["N4"] = [r["N4"] for r in results]
            df_items["Match_Type"] = [r["status"] for r in results]
            df_items["Matched_Terms"] = [", ".join(r["matched_terms"]) for r in results]
            df_items["Match_Score"] = [r["ml_confidence"] for r in results]
            df_items["Classification_Source"] = [r["classification_source"] for r in results]
            
            # New column: Ambiguous_Options (shows divergent options for ambiguous cases)
            df_items["Ambiguous_Options"] = [
                " | ".join(r.get("ambiguous_options", [])) if r["status"] == "Ambíguo" else ""
                for r in results
            ]
            
            df_items["Needs_Review"] = df_items["Match_Type"].isin(["Ambíguo", "Nenhum"])
            
            # Build summary
            total_items = len(df_items)
            unique_count = int((df_items["Match_Type"] == "Único").sum())
            ambiguous_count = int((df_items["Match_Type"] == "Ambíguo").sum())
            unmatched_count = int((df_items["Match_Type"] == "Nenhum").sum())
            
            summary = {
                "total_linhas": total_items,
                "coluna_descricao_utilizada": desc_column,
                "unico": unique_count,
                "ambiguo": ambiguous_count,
                "nenhum": unmatched_count,
            }
            
            # Generate analytics
            analytics = generate_analytics(df_items)
            
            # 7. Prepare and Return Response
            # Only convert first 1000 to dict for front-end safety (JSON response size)
            items_preview = df_items.head(1000).drop(columns=["_desc_norm"], errors="ignore").to_dict(orient="records")
            
            result = {
                "items": items_preview,
                "summary": summary,
                "analytics": analytics,
            }
            
            # NOTE: We keep the full df_items for Excel generation below!
        else:
            logging.info("Using dictionary-only classifier")
            # Only convert to dict if we are actually using the dictionary-only path
            item_records = df_items.to_dict(orient="records")
            from src.taxonomy_engine import classify_items
            result = classify_items(
                dict_records=dict_records,
                item_records=item_records,
                desc_column="Item_Description",
                col_desc_candidates=COL_DESC_CANDIDATES_DEFAULT,
            )
    except Exception as e:
        logging.error(f"Error classifying items: {e}")
        import traceback
        traceback.print_exc()
        return func.HttpResponse(
            f"Error classifying items: {str(e)}",
            status_code=500
        )

    logging.info("===== FINAL CLASSIFICATION SUMMARY =====")
    try:
        logging.info(safe_json_dumps(result["summary"]))
    except Exception as e:
        logging.error(f"Error logging summary: {type(e).__name__}: {e}")

    def write_analytics_to_excel(writer, analytics, sheet_name='Analytics'):
        """Helper function to write analytics tables with spacing."""
        row_offset = 0
        analytics_keys = ['pareto', 'gaps', 'ambiguity']
        
        for key in analytics_keys:
            if analytics.get(key):
                df = pd.DataFrame(analytics[key])
                df.to_excel(writer, sheet_name=sheet_name, index=False, startrow=row_offset)
                row_offset += len(df) + 3  # Add spacing between tables
        
        return row_offset

    try:
        # CRITICAL FIX: Use df_items (FULL) for Excel, not result["items"] (TRUNCATED PREVIEW)
        df_result = df_items.copy()
        
        # Clean up internal columns used for processing
        cols_to_drop = ["_desc_original", "_desc_norm", "Ambiguous_Options"]
        df_result = df_result.drop(columns=[c for c in cols_to_drop if c in df_result.columns])
        
        # Generate Excel with multiple sheets
        output = io.BytesIO()
        try:
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                # Sheet 1: Classification
                df_result.to_excel(writer, index=False, sheet_name='Classificação')
                
                # Sheet 2: Analytics (using helper function)
                analytics = result.get("analytics", {})
                write_analytics_to_excel(writer, analytics)
        finally:
            # Ensure BytesIO is properly handled even if error occurs
            output.seek(0)
        xlsx_bytes = output.getvalue()
        xlsx_base64 = base64.b64encode(xlsx_bytes).decode("utf-8")
        
        # Generate filename with timestamp (BRT - UTC-3)
        timestamp_utc = datetime.utcnow()
        timestamp_brt = timestamp_utc - timedelta(hours=3)
        timestamp = timestamp_brt.strftime("%Y%m%d_%H%M%S")
        
        if original_filename:
            # Strip extension and sanitize filename
            base_name = original_filename.rsplit('.', 1)[0] if '.' in original_filename else original_filename
            base_name = base_name.replace(' ', '_').replace('/', '_').replace('\\', '_')
            filename = f"{base_name}_classified_{timestamp}.xlsx"
        else:
            filename = f"spend_analysis_classified_{timestamp}.xlsx"
        
        logging.info(f"Excel generated: {len(xlsx_bytes)} bytes, {len(df_result)} rows, filename: {filename}")
        
        # Send to Power Automate for SharePoint logging (non-blocking, errors logged but not raised)
        send_to_power_automate(filename, xlsx_base64)
        
    except Exception as e:
        logging.error(f"Error generating Excel: {e}")
        return func.HttpResponse(
            f"Error generating Excel: {str(e)}",
            status_code=500
        )

    try:
        # Prepare truncated analytics for JSON response (to avoid token limits in Copilot)
        analytics_full = result.get("analytics", {})
        analytics_json = {
            "pareto": analytics_full.get("pareto", [])[:20],  # Top 20 categories (Legacy N4)
            "pareto_N1": analytics_full.get("pareto_N1", [])[:20],
            "pareto_N2": analytics_full.get("pareto_N2", [])[:20],
            "pareto_N3": analytics_full.get("pareto_N3", [])[:20],
            "pareto_N4": analytics_full.get("pareto_N4", [])[:20],
            "gaps": analytics_full.get("gaps", [])[:10],      # Top 10 gaps
            "ambiguity": analytics_full.get("ambiguity", [])[:10] # Top 10 ambiguities
        }

        response_data = {
            "status": "success",
            "sessionId": session_id,
            "fileContent": xlsx_base64,
            "filename": filename,
            "summary": result["summary"],
            "analytics": analytics_json,
            "items": result["items"],  # Already truncated to 1000 in Step 7
            "timestamp": timestamp,
            "encoding": "base64"
        }
        
        logging.info(f"Process completed successfully. Keys in response: {list(response_data.keys())}")
        if response_data.get("summary"):
            logging.info(f"Summary data being sent: {response_data['summary']}")
        
        return func.HttpResponse(
            body=safe_json_dumps(response_data),
            status_code=200,
            mimetype="application/json",
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            }
        )
        
    except Exception as e:
        logging.error(f"Error preparing response: {e}")
        return func.HttpResponse(
            f"Error preparing response: {str(e)}",
            status_code=500,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            }
        )

@app.route(
    route="TrainModel",
    methods=["POST", "OPTIONS"],
    auth_level=func.AuthLevel.ANONYMOUS
)
def TrainModel(req: func.HttpRequest) -> func.HttpResponse:
    import pandas as pd
    """
    Train a model for a specific sector using a provided classification file.
    Generates a 'Raw' file for testing as well.

    Request Body:
    - fileContent: Base64 encoded Excel/CSV (Final Classification).
    - sector: Sector name.
    
    Returns:
    - status: success/error
    - rawFileContent: Base64 of the generated Raw file (only descriptions).
    - report: Training report text.
    """
    if req.method == "OPTIONS":
        return func.HttpResponse(
            status_code=200,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            }
        )
        
    logging.info('TrainModel HTTP trigger function processed a request.')
    
    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse("Invalid JSON body", status_code=400)
    
    file_content_b64 = body.get("fileContent")
    sector = body.get("sector")
    filename = body.get("filename", "dataset.csv") # Default if not provided
    
    if not file_content_b64 or not sector:
        return func.HttpResponse("Missing fileContent or sector", status_code=400)

    # Handle 'Padrão' Sector (RAG Memory Ingestion)
    if sector == "Padrão" or sector == "Padrao":
        logging.info("Sector is 'Padrão'. Initiating Memory Ingestion (RAG)...")
        
        try:
            import base64
            import tempfile
            import uuid
            import os
            import json
            from src.memory_engine import MemoryEngine

            # Decode Base64
            file_data = base64.b64decode(file_content_b64)
            
            temp_path = os.path.join(tempfile.gettempdir(), f"train_memory_{uuid.uuid4()}.xlsx")
            with open(temp_path, "wb") as f:
                f.write(file_data)
            
            # Call Memory Engine
            engine = MemoryEngine()
            result = engine.ingest(temp_path)
            
            # Cleanup
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
            if result['success']:
                return func.HttpResponse(
                    json.dumps({
                        "message": result['message'],
                        "accuracy": 1.0, # Dummy metrics for frontend compatibility
                        "f1_score": 1.0,
                        "confusion_matrix": "N/A - Regras Aprendidas",
                        "classification_report": "Memória Atualizada"
                    }),
                    mimetype="application/json",
                    status_code=200,
                    headers={
                        "Access-Control-Allow-Origin": "*",
                        "Access-Control-Allow-Methods": "POST, OPTIONS",
                        "Access-Control-Allow-Headers": "Content-Type"
                    }
                )
            else:
                return func.HttpResponse(
                    f"Erro na ingestão de memória: {result['message']}", 
                    status_code=500,
                    headers={
                        "Access-Control-Allow-Origin": "*",
                        "Access-Control-Allow-Methods": "POST, OPTIONS",
                        "Access-Control-Allow-Headers": "Content-Type"
                    }
                )
                
        except Exception as e:
            logging.error(f"Error in memory ingestion: {e}")
            return func.HttpResponse(
                f"Erro interno na memória: {str(e)}", 
                status_code=500,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "POST, OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type"
                }
            )

    # Standard ML Training logic (Original)
    sector = sector.strip().capitalize()
    
    # Decode file
    try:
        file_bytes = base64.b64decode(file_content_b64)
        # Try Excel then CSV (similar logic to ProcessTaxonomy)
        try:
            df = pd.read_excel(io.BytesIO(file_bytes))
        except:
            try:
                df = pd.read_csv(io.BytesIO(file_bytes), sep=';', encoding='utf-8', on_bad_lines='skip')
            except:
                df = pd.read_csv(io.BytesIO(file_bytes), sep=',', encoding='utf-8', on_bad_lines='skip')
    except Exception as e:
        return func.HttpResponse(f"Error reading file: {e}", status_code=400)
        
    # Validate required columns
    # We need Description and N4 (Ground Truth)
    from src.taxonomy_engine import normalize_text
    
    # Normalization helper
    def normalize_header(header):
        import unicodedata
        normalized = unicodedata.normalize('NFD', str(header)).encode('ascii', 'ignore').decode('utf-8').lower().strip()
        if normalized in ['descricao', 'item_description', 'description', 'desc']: return 'Descrição'
        if normalized in ['n1', 'nivel 1', 'level 1', 'categoria']: return 'N1'
        if normalized in ['n2', 'nivel 2', 'level 2', 'subcategoria1']: return 'N2'
        if normalized in ['n3', 'nivel 3', 'level 3', 'subcategoria2']: return 'N3'
        if normalized in ['n4', 'nivel 4', 'level 4', 'subcategoria']: return 'N4'
        return header

    # Rename columns to standard
    df.rename(columns=lambda x: normalize_header(x), inplace=True)

    # New Standard: Descrição, N1, N2, N3, N4
    required_cols = ["Descrição", "N1", "N2", "N3", "N4"]
    missing = [c for c in required_cols if c not in df.columns]
    
    if missing:
        return func.HttpResponse(f"Missing required columns: {missing}. Expected 'Descrição', 'N1', 'N2', 'N3', 'N4'.", status_code=400)
        
    logging.info(f"Training using Description='Descrição' and Label='N4'")
    
    # Prepare DataFrame for training
    df["Item_Description"] = df["Descrição"].fillna("") # internal constant
    df["Descrição_Normalizada"] = df["Item_Description"].map(normalize_text)
    
    # Filter only rows with valid N4
    df_new = df[df["N4"].notna() & (df["N4"] != "") & (df["N4"] != "Nenhum") & (df["N4"] != "Ambíguo")].copy()
    
    if len(df_new) < 1:
        return func.HttpResponse(f"No valid classified data found in uploaded file.", status_code=400)

    # --- CUMULATIVE TRAINING LOGIC ---
    sector_lower = sector.lower()
    sector_dir = os.path.join(MODELS_DIR, sector_lower)
    os.makedirs(sector_dir, exist_ok=True)
    
    master_file = os.path.join(sector_dir, "dataset_master.csv")
    
    df_master = pd.DataFrame()
    logging.warning(f"[TRAIN DEBUG] Looking for master file at: {master_file}")
    logging.warning(f"[TRAIN DEBUG] File exists: {os.path.exists(master_file)}")
    
    if os.path.exists(master_file):
        try:
            # Read with explicit encoding
            df_master = pd.read_csv(master_file, encoding='utf-8')
            logging.warning(f"[TRAIN DEBUG] Loaded master: {len(df_master)} rows, empty={df_master.empty}")
            if 'added_version' in df_master.columns:
                version_counts = df_master['added_version'].value_counts().to_dict()
                logging.warning(f"[TRAIN DEBUG] Versions in loaded master: {version_counts}")
        except Exception as e:
            logging.error(f"[TRAIN DEBUG] ERROR reading master: {e}")
            logging.warning(f"Could not read master dataset: {e}. Starting fresh.")
    else:
        logging.warning(f"[TRAIN DEBUG] Master file does NOT exist, starting fresh")
    
    # Standardize columns for master dataset
    # Now includes full hierarchy (N1, N2, N3, N4) for complete traceability
    cols_to_keep = ['Descrição', 'N1', 'N2', 'N3', 'N4', 'Descrição_Normalizada']
    
    # Determine next version number for tracking
    history_file = os.path.join(sector_dir, "model_history.json")
    next_version = "v_1"
    if os.path.exists(history_file):
        try:
            with open(history_file, 'r') as f:
                history = json.load(f)
                if history:
                    existing_versions = [int(h.get("version_id", "v_0").replace("v_", "")) for h in history]
                    next_version = f"v_{max(existing_versions) + 1}"
        except:
            pass
    
    # Ensure new data has these columns + tracking columns
    df_new_subset = df_new[cols_to_keep].copy()
    df_new_subset['added_version'] = next_version
    df_new_subset['added_at'] = datetime.now().isoformat()
    
    # Concatenate with existing master dataset
    if not df_master.empty:
        logging.info(f"Existing master has {len(df_master)} rows")
        
        # Ensure master has Descrição_Normalizada column (for deduplication)
        if 'Descrição_Normalizada' not in df_master.columns and 'Descrição' in df_master.columns:
            df_master['Descrição_Normalizada'] = df_master['Descrição'].map(normalize_text)
            logging.info("Created Descrição_Normalizada column for existing master")
        
        # Add legacy tracking columns if missing
        if 'added_version' not in df_master.columns:
            df_master['added_version'] = 'legacy'
        if 'added_at' not in df_master.columns:
            df_master['added_at'] = ''
        
        # Ensure both dataframes have same columns before concat
        all_cols = list(set(df_master.columns.tolist() + df_new_subset.columns.tolist()))
        for col in all_cols:
            if col not in df_master.columns:
                df_master[col] = ''
            if col not in df_new_subset.columns:
                df_new_subset[col] = ''
        
        df_combined = pd.concat([df_master, df_new_subset], ignore_index=True)
        logging.info(f"Combined dataset: {len(df_master)} (existing) + {len(df_new_subset)} (new) = {len(df_combined)} rows")
    else:
        df_combined = df_new_subset
        logging.info(f"No existing master, starting with {len(df_combined)} rows")
        
    # Deduplicate
    # Criteria: Same Normalized Description AND Same N4. 
    # IMPORTANT: keep='first' preserves original training data (v1, v2, etc.)
    # and only adds truly NEW unique items from the new file.
    # This prevents overwriting historical training data with identical new uploads.
    before_dedup = len(df_combined)
    df_combined.drop_duplicates(subset=['Descrição_Normalizada', 'N4'], keep='first', inplace=True)
    
    logging.info(f"Deduplication: {before_dedup} -> {len(df_combined)} rows")
    
    # Check versions in combined dataset
    if 'added_version' in df_combined.columns:
        version_counts = df_combined['added_version'].value_counts().to_dict()
        logging.info(f"Rows per version after dedup: {version_counts}")
    
    # Save Master (KEEP Descrição_Normalizada for future deduplication)
    df_combined.to_csv(master_file, index=False)
    logging.info(f"Saved master dataset with {len(df_combined)} rows")
    
    logging.info(f"Master dataset updated with {len(df_combined)} rows.")

    # --- RETRAIN MODEL (Sync or Async?) ---
    # For now, synchronous to ensure immediate feedback, but this might timeout for large datasets.
    # ideally trigger an async process.
    # Re-training...
    from src.model_trainer import train_model
    
    try:
        logging.info(f"Starting model training for sector {sector}...")
        report = train_model(sector=sector, dataset_path=master_file, models_dir=MODELS_DIR)
        logging.info("Training completed successfully.")
        
        return func.HttpResponse(
            body=safe_json_dumps({
                "status": "success",
                "message": f"Modelo para setor '{sector}' treinado com sucesso!",
                "version": next_version,
                "total_samples": len(df_combined),
                "report": report
            }),
            status_code=200,
            mimetype="application/json",
             headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            }
        )
    except Exception as e:
        logging.error(f"Training failed: {e}")
        return func.HttpResponse(f"Error during training: {e}", status_code=500)


@app.route(
    route="GetModelHistory",
    methods=["GET", "OPTIONS"],
    auth_level=func.AuthLevel.ANONYMOUS
)
def GetModelHistory(req: func.HttpRequest) -> func.HttpResponse:
    """
    Get training history for a sector.
    """
    if req.method == "OPTIONS":
        return func.HttpResponse(
            status_code=200,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            }
        )
        
    sector = req.params.get("sector")
    if not sector:
        return func.HttpResponse("Missing 'sector' query parameter", status_code=400)
        
    sector = sector.strip().lower()
    history_file = os.path.join(MODELS_DIR, sector, "model_history.json")
    
    if not os.path.exists(history_file):
        return func.HttpResponse(
            json.dumps([]),
            status_code=200,
            mimetype="application/json",
            headers={
                "Access-Control-Allow-Origin": "*"
            }
        )
        
    try:
        with open(history_file, 'r') as f:
            history = json.load(f)
        return func.HttpResponse(
            body=safe_json_dumps(history),
            status_code=200,
            mimetype="application/json",
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            }
        )
    except Exception as e:
        return func.HttpResponse(f"Error fetching history: {str(e)}", status_code=500)

@app.route(
    route="SetActiveModel",
    methods=["POST", "OPTIONS"],
    auth_level=func.AuthLevel.ANONYMOUS
)
def SetActiveModel(req: func.HttpRequest) -> func.HttpResponse:
    import pandas as pd
    if req.method == "OPTIONS":
        return func.HttpResponse(status_code=204, headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        })

    try:
        req_body = req.get_json()
        sector = req_body.get('sector')
        version_id = req_body.get('version_id')
        
        if not sector or not version_id:
            return func.HttpResponse("Missing sector or version_id", status_code=400)
            
        sector_dir = os.path.join(MODELS_DIR, sector.lower())
        version_dir = os.path.join(sector_dir, "versions", version_id)
        
        if not os.path.exists(version_dir):
            return func.HttpResponse(f"Version {version_id} not found", status_code=404)
            
        import shutil
        # Copy artifacts from version to root
        shutil.copy(f"{version_dir}/tfidf_vectorizer.pkl", f"{sector_dir}/tfidf_vectorizer.pkl")
        shutil.copy(f"{version_dir}/classifier.pkl", f"{sector_dir}/classifier.pkl")
        shutil.copy(f"{version_dir}/label_encoder.pkl", f"{sector_dir}/label_encoder.pkl")
        
        # Also restore hierarchy if versioned copy exists
        versioned_hierarchy = f"{version_dir}/n4_hierarchy.json"
        if os.path.exists(versioned_hierarchy):
            shutil.copy(versioned_hierarchy, f"{sector_dir}/n4_hierarchy.json")
            logging.info(f"Restored n4_hierarchy.json from {version_id}")

        # Update model_history.json to reflect active status
        history_file = f"{sector_dir}/model_history.json"
        if os.path.exists(history_file):
            try:
                with open(history_file, 'r') as f:
                    history = json.load(f)
                
                # Update statuses
                for h in history:
                    if h.get('version_id') == version_id:
                        h['status'] = 'active'
                    else:
                        h['status'] = 'inactive'
                
                with open(history_file, 'w') as f:
                    json.dump(history, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logging.error(f"Error updating model history status: {e}")
        
        return func.HttpResponse(
            body=safe_json_dumps({"message": f"Successfully rolled back to {version_id}"}),
            status_code=200,
            mimetype="application/json",
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            }
        )
        
    except Exception as e:
        logging.error(f"Error setting active model: {e}")
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


def _load_hierarchy_with_fallback(sector_dir, version_id):
    hierarchy = {}
    hierarchy_loaded = False
    
    # Try to load version-specific hierarchy
    if version_id and version_id != "active":
            version_hierarchy = os.path.join(sector_dir, "versions", version_id, "n4_hierarchy.json")
            if os.path.exists(version_hierarchy):
                try:
                    with open(version_hierarchy, 'r', encoding='utf-8') as f:
                        hierarchy = json.load(f)
                    hierarchy_loaded = True
                except:
                    pass
    
    # Fallback to CSV reconstruction
    if not hierarchy_loaded and version_id and version_id != "active":
        training_file = os.path.join(sector_dir, "dataset_master.csv")
        if os.path.exists(training_file):
            try:
                df = pd.read_csv(training_file)
                if 'added_version' in df.columns:
                    def get_version_num(v):
                        try:
                            return int(str(v).replace('v_', '').replace('legacy', '0'))
                        except:
                            return 0
                    
                    target_v = get_version_num(version_id)
                    df['_v'] = df['added_version'].apply(get_version_num)
                    df_filtered = df[df['_v'] <= target_v]
                    
                    if len(df_filtered) > 0 and 'N4' in df_filtered.columns:
                        for _, row in df_filtered[['N1', 'N2', 'N3', 'N4']].drop_duplicates().iterrows():
                            n4 = str(row['N4']).strip()
                            if pd.notna(n4) and n4:
                                hierarchy[n4] = {
                                    'N1': str(row['N1']).strip() if pd.notna(row['N1']) else '',
                                    'N2': str(row['N2']).strip() if pd.notna(row['N2']) else '',
                                    'N3': str(row['N3']).strip() if pd.notna(row['N3']) else ''
                                }
                        hierarchy_loaded = True
            except Exception as e:
                logging.warning(f"Failed to reconstruct hierarchy from CSV: {e}")

    # Fallback to root
    if not hierarchy_loaded:
        hierarchy_file = os.path.join(sector_dir, "n4_hierarchy.json")
        if os.path.exists(hierarchy_file):
            try:
                with open(hierarchy_file, 'r', encoding='utf-8') as f:
                    hierarchy = json.load(f)
            except:
                pass
    
    return hierarchy

@app.route(
    route="GetModelInfo",
    methods=["GET", "OPTIONS"],
    auth_level=func.AuthLevel.ANONYMOUS
)
def GetModelInfo(req: func.HttpRequest) -> func.HttpResponse:
    import pandas as pd
    """
    Get detailed information about a model version including hierarchy, stats and metrics.
    
    Query params:
    - sector: Sector name (required)
    - version_id: Version ID (optional, defaults to active version)
    """
    if req.method == "OPTIONS":
        return func.HttpResponse(status_code=204, headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        })

    sector = req.params.get("sector")
    version_id = req.params.get("version_id")
    
    if not sector:
        return func.HttpResponse("Missing 'sector' parameter.", status_code=400)
    
    try:
        sector_dir = os.path.join(MODELS_DIR, sector.lower())
        training_dir = os.path.join(os.path.dirname(__file__), "training", sector.lower())
        
        # Load hierarchy using helper
        hierarchy = _load_hierarchy_with_fallback(sector_dir, version_id)
        tree = {}

        # Build tree structure N1 -> N2 -> N3 -> [N4s]
        for n4, levels in hierarchy.items():
            n1 = levels.get('N1', 'Outros')
            n2 = levels.get('N2', 'Outros')
            n3 = levels.get('N3', 'Outros')
            
            if n1 not in tree:
                tree[n1] = {}
            if n2 not in tree[n1]:
                tree[n1][n2] = {}
            if n3 not in tree[n1][n2]:
                tree[n1][n2][n3] = []
            if n4 not in tree[n1][n2][n3]:
                tree[n1][n2][n3].append(n4)
        
        # Count unique levels
        n1s = set()
        n2s = set()
        n3s = set()
        n4s = set()
        for n4, levels in hierarchy.items():
            n1s.add(levels.get('N1', ''))
            n2s.add(levels.get('N2', ''))
            n3s.add(levels.get('N3', ''))
            n4s.add(n4)
            
        # Initialize data holders
        training_stats = {
            "total_descriptions": 0,
            "by_n4": []
        }
        comparison = None
        metrics = {}
        active_version = None
        
        # Load Dataset Master (for stats and dynamic comparison)
        training_file = os.path.join(sector_dir, "dataset_master.csv")
        df_master = None
        if os.path.exists(training_file):
            try:
                df_master = pd.read_csv(training_file)
            except Exception as e:
                logging.warning(f"Error loading training data: {e}")

        # Helper to calculate stats from DF for a version
        def calc_stats_from_df(df, target_ver):
            count = 0
            n4_top = []
            if df is not None and 'added_version' in df.columns:
                def get_version_num(v):
                    try:
                        return int(str(v).replace('v_', '').replace('legacy', '0'))
                    except:
                        return 0
                
                target_v_num = get_version_num(target_ver)
                if '_version_num' not in df.columns:
                    df['_version_num'] = df['added_version'].apply(get_version_num)
                
                df_filtered = df[df['_version_num'] <= target_v_num]
                count = len(df_filtered)
                
                if 'N4' in df_filtered.columns:
                    n4_counts = df_filtered['N4'].value_counts().head(50)
                    n4_top = [{"N4": n4, "count": int(c)} for n4, c in n4_counts.items()]
            elif df is not None:
                # Fallback if no versioning column
                count = len(df)
                if 'N4' in df.columns:
                     n4_counts = df['N4'].value_counts().head(50)
                     n4_top = [{"N4": n4, "count": int(c)} for n4, c in n4_counts.items()]
            return count, n4_top

        # Load Model History (for metrics and version identifying)
        history_file = os.path.join(sector_dir, "model_history.json")
        history = []
        if os.path.exists(history_file):
            try:
                with open(history_file, 'r') as f:
                    history = json.load(f)
            except: pass

        # Determine target version ID (if not provided, find active)
        target_vid = version_id
        if not target_vid:
            # Find active in history
            for h in history:
                if h.get('status') == 'active':
                    active_version = h.get('version_id')
                    target_vid = active_version
                    break
            if not target_vid and history:
                target_vid = history[0]['version_id'] # Fallback to latest

        # Get metrics for target version
        curr_idx = -1
        if target_vid:
            for i, h in enumerate(history):
                if h['version_id'] == target_vid:
                    metrics = h.get('metrics', {})
                    curr_idx = i
                    break
        
        # Calculate current training stats (Dynamic from CSV)
        curr_samples, curr_n4_top = calc_stats_from_df(df_master, target_vid)
        training_stats["total_descriptions"] = curr_samples
        training_stats["by_n4"] = curr_n4_top

        # Comparison Logic
        if curr_idx != -1 and curr_idx + 1 < len(history):
            prev = history[curr_idx + 1]
            prev_vid = prev['version_id']
            prev_metrics = prev.get('metrics', {})
            
            # Recalculate previous samples from CSV (to be consistent with current)
            prev_samples, _ = calc_stats_from_df(df_master, prev_vid)
            
            # Load previous hierarchy to compare counts
            prev_hierarchy = _load_hierarchy_with_fallback(sector_dir, prev_vid)
            p_n1s = set(levels.get('N1', '') for levels in prev_hierarchy.values())
            p_n2s = set(levels.get('N2', '') for levels in prev_hierarchy.values())
            p_n3s = set(levels.get('N3', '') for levels in prev_hierarchy.values())
            p_n4s = set(prev_hierarchy.keys())
            
            comparison = {
                "previous_version": prev_vid,
                "metrics": {
                    "accuracy": prev_metrics.get('accuracy', 0),
                    "f1_macro": prev_metrics.get('f1_macro', 0),
                    "total_samples": prev_samples, # Use Calculated!
                    "n1_count": len(p_n1s),
                    "n2_count": len(p_n2s),
                    "n3_count": len(p_n3s),
                    "n4_count": len(p_n4s)
                }
            }

        response = {
            "sector": sector,
            "version_id": target_vid or "unknown",
            "hierarchy": {
                "N1_count": len(n1s),
                "N2_count": len(n2s),
                "N3_count": len(n3s),
                "N4_count": len(n4s),
                "tree": tree
            },
            "training_stats": training_stats,
            "metrics": metrics,
            "comparison": comparison
        }
        
        return func.HttpResponse(
            body=safe_json_dumps(response),
            status_code=200,
            mimetype="application/json",
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            }
        )
        
    except Exception as e:
        logging.error(f"Error getting model info: {e}")
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


@app.route(
    route="GetTrainingData",
    methods=["GET", "OPTIONS"],
    auth_level=func.AuthLevel.ANONYMOUS
)
def GetTrainingData(req: func.HttpRequest) -> func.HttpResponse:
    import pandas as pd
    """
    Get paginated training data from dataset_master.csv.
    
    Query params:
    - sector: Sector name (required)
    - page: Page number (default: 1)
    - page_size: Items per page (default: 50, max: 200)
    - version: Filter by added_version (optional)
    - n4: Filter by N4 category (optional)
    - search: Search text in description (optional)
    """
    if req.method == "OPTIONS":
        return func.HttpResponse(status_code=204, headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        })

    sector = req.params.get("sector")
    if not sector:
        return func.HttpResponse("Missing 'sector' parameter.", status_code=400)
    
    try:
        page = int(req.params.get("page", 1))
        page_size = min(int(req.params.get("page_size", 50)), 200)
        version_filter = req.params.get("version")
        n4_filter = req.params.get("n4")
        search_filter = req.params.get("search")
        
        sector_dir = os.path.join(MODELS_DIR, sector.lower())
        master_file = os.path.join(sector_dir, "dataset_master.csv")
        
        if not os.path.exists(master_file):
            return func.HttpResponse(
                body=safe_json_dumps({"data": [], "total": 0, "page": page, "page_size": page_size}),
                status_code=200,
                mimetype="application/json",
                headers={"Access-Control-Allow-Origin": "*"}
            )
        
        df = pd.read_csv(master_file)
        
        # Group duplicates and count occurrences (user-friendly view)
        # Deduplicate by (Descrição, N4, version) - show unique items per version
        df['_count'] = df.groupby(['Descrição', 'N4', 'added_version'])['Descrição'].transform('count')
        
        # Deduplicate for display (keep first occurrence per version)
        df_display = df.drop_duplicates(subset=['Descrição', 'N4', 'added_version'], keep='first').copy()
        df_display.rename(columns={'_count': 'Ocorrências'}, inplace=True)
        
        # Apply filters
        if version_filter:
            df_display = df_display[df_display['added_version'] == version_filter]
        if n4_filter:
            df_display = df_display[df_display['N4'] == n4_filter]
        if search_filter:
            df_display = df_display[df_display['Descrição'].str.contains(search_filter, case=False, na=False)]
        
        total = len(df_display)
        total_with_duplicates = len(df)  # Total real for info
        
        # Paginate
        start = (page - 1) * page_size
        end = start + page_size
        df_page = df_display.iloc[start:end]
        
        # Add row index for deletion
        df_page = df_page.reset_index()
        df_page.rename(columns={'index': 'row_id'}, inplace=True)
        
        data = df_page.to_dict('records')
        
        # Get unique versions for filter dropdown
        versions = df['added_version'].dropna().unique().tolist() if 'added_version' in df.columns else []
        
        response = {
            "data": data,
            "total": total,
            "total_with_duplicates": total_with_duplicates,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
            "versions": versions
        }
        
        return func.HttpResponse(
            body=safe_json_dumps(response),
            status_code=200,
            mimetype="application/json",
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            }
        )
        
    except Exception as e:
        logging.error(f"Error getting training data: {e}")
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


@app.route(
    route="DeleteTrainingData",
    methods=["POST", "OPTIONS"],
    auth_level=func.AuthLevel.ANONYMOUS
)
def DeleteTrainingData(req: func.HttpRequest) -> func.HttpResponse:
    import pandas as pd
    """
    Delete training data rows from dataset_master.csv.
    
    Body:
    - sector: Sector name (required)
    - row_ids: List of row indices to delete (optional, legacy)
    - version: Delete all rows from this version (optional)
    - items: List of {descricao, n4, version} to delete all occurrences (optional)
    """
    if req.method == "OPTIONS":
        return func.HttpResponse(status_code=204, headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        })

    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse("Invalid JSON body", status_code=400)
    
    sector = body.get("sector")
    row_ids = body.get("row_ids", [])
    version = body.get("version")
    items = body.get("items", [])  # New: list of {descricao, n4, version}
    
    if not sector:
        return func.HttpResponse("Missing 'sector' parameter.", status_code=400)
    
    if not row_ids and not version and not items:
        return func.HttpResponse("Must provide 'row_ids', 'version', or 'items' to delete.", status_code=400)
    
    try:
        sector_dir = os.path.join(MODELS_DIR, sector.lower())
        master_file = os.path.join(sector_dir, "dataset_master.csv")
        
        if not os.path.exists(master_file):
            return func.HttpResponse("No training data found.", status_code=404)
        
        df = pd.read_csv(master_file)
        original_count = len(df)
        
        if version:
            # Delete all rows from a specific version
            df = df[df['added_version'] != version]
            deleted_count = original_count - len(df)
            
            # Also remove from model_history.json and delete version folder
            history_file = os.path.join(sector_dir, "model_history.json")
            if os.path.exists(history_file):
                with open(history_file, 'r') as f:
                    history = json.load(f)
                
                # Check if we're deleting the active version
                was_active = any(h.get('version_id') == version and h.get('status') == 'active' for h in history)
                
                # Remove version from history
                history = [h for h in history if h.get('version_id') != version]
                
                # If we deleted the active version, activate the next most recent
                if was_active and history:
                    history[0]['status'] = 'active'
                    # Restore the now-active version's model and hierarchy
                    new_active_version = history[0]['version_id']
                    version_dir = os.path.join(sector_dir, "versions", new_active_version)
                    
                    # Copy model file
                    version_model = os.path.join(version_dir, "model.pkl")
                    active_model = os.path.join(sector_dir, "model.pkl")
                    if os.path.exists(version_model):
                        shutil.copy2(version_model, active_model)
                    
                    # Copy hierarchy file
                    version_hierarchy = os.path.join(version_dir, "n4_hierarchy.json")
                    active_hierarchy = os.path.join(sector_dir, "n4_hierarchy.json")
                    if os.path.exists(version_hierarchy):
                        shutil.copy2(version_hierarchy, active_hierarchy)
                
                # Save updated history
                with open(history_file, 'w') as f:
                    json.dump(history, f, indent=2, ensure_ascii=False)
                
                # Delete the version folder
                version_folder = os.path.join(sector_dir, "versions", version)
                if os.path.exists(version_folder):
                    shutil.rmtree(version_folder)
        elif items:
            # Delete by specific items (descricao + n4 + version) - removes all duplicates
            for item in items:
                desc = item.get('descricao') or item.get('Descrição')
                n4 = item.get('n4') or item.get('N4')
                item_version = item.get('version') or item.get('added_version')
                
                if desc and n4 and item_version:
                    # Remove ALL rows matching this combination
                    mask = (df['Descrição'] == desc) & (df['N4'] == n4) & (df['added_version'] == item_version)
                    df = df[~mask]
            
            deleted_count = original_count - len(df)
        else:
            # Delete by row indices (legacy)
            df = df.drop(index=row_ids, errors='ignore')
            deleted_count = original_count - len(df)
        
        # Save updated file
        df.to_csv(master_file, index=False)
        
        response = {
            "message": f"Deleted {deleted_count} rows",
            "remaining": len(df)
        }
        
        return func.HttpResponse(
            body=json.dumps(response),
            status_code=200,
            mimetype="application/json",
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            }
        )
        
    except Exception as e:
        logging.error(f"Error deleting training data: {e}")
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)

@app.route(route="SearchMemory", auth_level=func.AuthLevel.ANONYMOUS, methods=["GET", "OPTIONS"])
def SearchMemory(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('SearchMemory HTTP trigger function processed a request.')
    
    if req.method == "OPTIONS":
        return func.HttpResponse(
            status_code=200,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            }
        )

    query = req.params.get('query', '')
    
    try:
        from src.memory_engine import MemoryEngine
        engine = MemoryEngine()
        results = engine.search(query)
        
        return func.HttpResponse(
            json.dumps(results),
            mimetype="application/json",
            status_code=200,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            }
        )
    except Exception as e:
        logging.error(f"Error searching memory: {e}")
        return func.HttpResponse(str(e), status_code=500)

@app.route(route="DeleteMemoryRule", auth_level=func.AuthLevel.ANONYMOUS, methods=["DELETE", "GET", "OPTIONS"])
def DeleteMemoryRule(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('DeleteMemoryRule HTTP trigger function processed a request.')
    
    if req.method == "OPTIONS":
        return func.HttpResponse(
            status_code=200,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "DELETE, GET, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            }
        )

    rule_id = req.params.get('id')
    if not rule_id:
        # Check body just in case
        try:
            body = req.get_json()
            rule_id = body.get('id')
        except:
            pass
            
    if not rule_id:
        return func.HttpResponse("Missing rule ID", status_code=400)
    
    try:
        from src.memory_engine import MemoryEngine
        engine = MemoryEngine()
        success = engine.delete_rule(rule_id)
        
        if success:
            return func.HttpResponse(
                json.dumps({"success": True}),
                mimetype="application/json",
                status_code=200,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "DELETE, GET, OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type"
                }
            )
        else:
            return func.HttpResponse("Rule not found", status_code=404)
    except Exception as e:
        logging.error(f"Error deleting memory rule: {e}")
        return func.HttpResponse(str(e), status_code=500)
