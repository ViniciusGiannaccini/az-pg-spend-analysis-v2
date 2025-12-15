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

import azure.functions as func
import pandas as pd

from src.taxonomy_engine import (
    classify_items,
    COL_DESC_CANDIDATES_DEFAULT,
)

# Import custom hierarchy mapper
from src.taxonomy_mapper import load_custom_hierarchy, apply_custom_hierarchy

# ML-enhanced classification (optional, falls back to dictionary-only if disabled)
USE_ML_CLASSIFIER = os.getenv("USE_ML_CLASSIFIER", "false").lower() == "true"

# Import ML functions if enabled (models loaded on-demand per sector)
if USE_ML_CLASSIFIER:
    try:
        from src.ml_classifier import load_model
        from src.hybrid_classifier import classify_hybrid
        logging.info("ML classification enabled. Models will be loaded on-demand per sector.")
    except Exception as e:
        logging.warning(f"Failed to import ML modules: {e}. Falling back to dictionary-only mode.")
        USE_ML_CLASSIFIER = False

# Power Automate Flow URL for saving classified files to SharePoint
POWER_AUTOMATE_URL = os.getenv("POWER_AUTOMATE_URL", "")
POWER_AUTOMATE_API_KEY = os.getenv("POWER_AUTOMATE_API_KEY", "")


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


app = func.FunctionApp()


@app.function_name(name="GetDirectLineToken")
@app.route(
    route="get-token",
    methods=["GET", "OPTIONS"],  # Adicionado OPTIONS para CORS preflight
    auth_level=func.AuthLevel.ANONYMOUS
)
def get_direct_line_token(req: func.HttpRequest) -> func.HttpResponse:
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
            json.dumps({"error": "Direct Line not configured"}),
            status_code=500,
            mimetype="application/json"
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
                body=json.dumps(conversation_data),
                status_code=200,
                mimetype="application/json",
                headers=headers
            )
        else:
            logging.error(f"Direct Line API error: {response.status_code} - {response.text}")
            return func.HttpResponse(
                json.dumps({"error": "Failed to create conversation"}),
                status_code=response.status_code,
                mimetype="application/json"
            )
            
    except requests.exceptions.RequestException as e:
        logging.error(f"Request to Direct Line API failed: {e}")
        return func.HttpResponse(
            json.dumps({"error": "Network error contacting Direct Line"}),
            status_code=500,
            mimetype="application/json"
        )
    except Exception as e:
        logging.error(f"Unexpected error in get_direct_line_token: {e}")
        return func.HttpResponse(
            json.dumps({"error": "Internal server error"}),
            status_code=500,
            mimetype="application/json"
        )


@app.function_name(name="ProcessTaxonomy")
@app.route(
    route="ProcessTaxonomy",
    methods=["POST", "OPTIONS"],  # Adicionado OPTIONS para CORS preflight
    auth_level=func.AuthLevel.ANONYMOUS
)
def process_taxonomy(req: func.HttpRequest) -> func.HttpResponse:
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
        body = req.get_json()
    except ValueError:
        body = {}

    file_content_b64 = body.get("fileContent")
    dict_content_b64 = body.get("dictionaryContent")
    sector = body.get("sector")
    original_filename = body.get("originalFilename", "")
    custom_hierarchy_b64 = body.get("customHierarchy")  # Optional custom hierarchy

    if not file_content_b64:
        return func.HttpResponse(
            "Parâmetro 'fileContent' (base64) é obrigatório no corpo da requisição.",
            status_code=400
        )

    if not dict_content_b64:
        return func.HttpResponse(
            "Parâmetro 'dictionaryContent' (base64) é obrigatório no corpo da requisição.",
            status_code=400
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

    try:
        df_items = pd.read_excel(io.BytesIO(file_bytes))
        logging.info("Successfully parsed file as Excel")
    except (pd.errors.ParserError, ValueError, KeyError) as e:
        # If Excel fails, try CSV with different delimiters
        logging.warning(f"Excel parsing failed ({type(e).__name__}), trying CSV with semicolon")
        try:
            # Try semicolon first (common in Brazil/Europe)
            df_items = pd.read_csv(io.BytesIO(file_bytes), sep=';', encoding='utf-8', on_bad_lines='skip')
            logging.info("Successfully parsed file as CSV with semicolon separator")
        except (pd.errors.ParserError, UnicodeDecodeError) as e2:
            logging.warning(f"Semicolon CSV parsing failed ({type(e2).__name__}), trying comma")
            try:
                # Try comma
                df_items = pd.read_csv(io.BytesIO(file_bytes), sep=',', encoding='utf-8', on_bad_lines='skip')
                logging.info("Successfully parsed file as CSV with comma separator")
            except Exception as e3:
                logging.error(f"All parsing attempts failed. Last error: {type(e3).__name__}: {e3}")
                return func.HttpResponse(
                    f"Error reading items file. Supported formats: Excel (.xlsx, .xls) or CSV (.csv) with ';' or ',' separator. Error: {str(e3)}",
                    status_code=500
                )

    try:
        # Parse dictionary as XLSX and read CONFIG sheet
        df_config = pd.read_excel(io.BytesIO(dict_bytes), sheet_name='CONFIG')
        logging.info(f"CONFIG sheet loaded: {len(df_config)} rows")
        
        # Lookup sector in CONFIG sheet to get dictionary sheet name
        # Filter out NaN rows and perform case-insensitive lookup
        df_config_valid = df_config.dropna(subset=['Setor'])
        sector_row = df_config_valid[df_config_valid['Setor'].str.strip().str.lower() == sector.strip().lower()]
        
        if sector_row.empty:
            available_sectors = df_config_valid['Setor'].dropna().tolist()
            logging.error(f"Sector '{sector}' not found in CONFIG sheet. Available sectors: {available_sectors}")
            return func.HttpResponse(
                f"Setor '{sector}' não encontrado na aba CONFIG. Setores disponíveis: {', '.join(available_sectors)}",
                status_code=400
            )
        
        dict_sheet_name = sector_row.iloc[0]['ABA_DICIONARIO']
        logging.info(f"Sector '{sector}' mapped to dictionary sheet: '{dict_sheet_name}'")
        
        # Read dictionary from the specified sheet
        try:
            df_dict = pd.read_excel(io.BytesIO(dict_bytes), sheet_name=dict_sheet_name)
            logging.info(f"Successfully loaded dictionary from sheet '{dict_sheet_name}': {len(df_dict)} rows, {len(df_dict.columns)} columns")
        except ValueError as e:
            logging.error(f"Dictionary sheet '{dict_sheet_name}' not found in XLSX file: {e}")
            return func.HttpResponse(
                f"Aba de dicionário '{dict_sheet_name}' não encontrada no arquivo XLSX.",
                status_code=500
            )
            
    except ValueError as e:
        if "CONFIG" in str(e):
            logging.error(f"CONFIG sheet not found in dictionary XLSX: {e}")
            return func.HttpResponse(
                "Aba 'CONFIG' não encontrada no arquivo de dicionário XLSX.",
                status_code=500
            )
        raise
    except Exception as e:
        logging.error(f"Error reading dictionary XLSX: {type(e).__name__}: {e}")
        return func.HttpResponse(
            f"Erro ao ler arquivo de dicionário XLSX: {str(e)}",
            status_code=500
        )

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
    item_records = df_items.to_dict(orient="records")

    try:
        # Use ML-enhanced hybrid classifier if enabled
        if USE_ML_CLASSIFIER:
            logging.info(f"Using ML hybrid classifier for sector: {sector}")
            
            # Create wrapper to process items in batch using hybrid classifier
            logging.info("Importing taxonomy engine...")
            from src.taxonomy_engine import build_patterns, normalize_text, generate_analytics
            
            logging.info("Building dictionary patterns...")
            # Build dictionary patterns
            patterns_by_n4, terms_by_n4, taxonomy_by_n4 = build_patterns(df_dict)
            
            logging.info("Loading ML models...")
            # Load ML models once
            from src.ml_classifier import load_model
            from src.hybrid_classifier import classify_hybrid
            logging.info(f"Attempting to load model for sector: {sector}")
            vectorizer, classifier, label_encoder, hierarchy = load_model(sector=sector)
            
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
            df_items["_desc_original"] = df_items[desc_column].fillna("")
            df_items["_desc_norm"] = df_items["_desc_original"].map(normalize_text)
            
            # Process each item with hybrid classifier
            results = []
            for _, row in df_items.iterrows():
                desc = row["_desc_original"]
                desc_norm = row["_desc_norm"]
                
                result = classify_hybrid(
                    description=desc,
                    sector=sector,
                    dict_patterns=patterns_by_n4,
                    dict_terms=terms_by_n4,
                    dict_taxonomy=taxonomy_by_n4,
                    desc_norm=desc_norm,
                    vectorizer=vectorizer,
                    classifier=classifier,
                    label_encoder=label_encoder,
                    hierarchy=hierarchy
                )
                
                results.append(result.to_dict())
            
            # Apply custom hierarchy if provided (with fallback to top candidates)
            if custom_hierarchy:
                for r in results:
                    # Build top_candidates list from result
                    top_candidates = r.get('top_candidates', [])
                    if not top_candidates and r.get('N4'):
                        # If no top_candidates, at least try the main N4
                        top_candidates = [{'N4': r['N4']}]
                    
                    # Try to find a matching N4 in custom hierarchy
                    custom_result, matched_n4 = apply_custom_hierarchy(top_candidates, custom_hierarchy)
                    
                    if custom_result:
                        # Found a match - use custom hierarchy
                        r['N1'] = custom_result.get('N1', '')
                        r['N2'] = custom_result.get('N2', '')
                        r['N3'] = custom_result.get('N3', '')
                        r['N4'] = custom_result.get('N4', '')
                    else:
                        # No match found in custom hierarchy - mark as unclassified
                        if r.get('status') == 'Único':
                            # Keep original classification in a note BEFORE clearing
                            original_n4 = r.get('N4', '')
                            r['N1'] = ''
                            r['N2'] = ''
                            r['N3'] = ''
                            r['N4'] = ''
                            r['status'] = 'Nenhum'
                            if original_n4:
                                r['matched_terms'] = [f'Original: {original_n4}']
            
            # Convert results to DataFrame columns
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
            
            # Prepare output
            items_output = df_items.drop(columns=["_desc_norm"]).to_dict(orient="records")
            
            result = {
                "items": items_output,
                "summary": summary,
                "analytics": analytics,
            }
        else:
            logging.info("Using dictionary-only classifier")
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
        logging.info(json.dumps(result["summary"], ensure_ascii=False, default=str))
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
        df_result = pd.DataFrame(result["items"])
        
        # Clean up internal columns used for processing
        if "_desc_original" in df_result.columns:
            df_result = df_result.drop(columns=["_desc_original"])
        
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
            "items": result["items"],  # Return all items for frontend context calculation
            "timestamp": timestamp,
            "encoding": "base64"
        }
        
        logging.info("Process completed successfully. Returning JSON (truncated analytics) + Excel (complete).")
        
        return func.HttpResponse(
            body=json.dumps(response_data, ensure_ascii=False),
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

@app.function_name(name="TrainModel")
@app.route(
    route="TrainModel",
    methods=["POST", "OPTIONS"],
    auth_level=func.AuthLevel.ANONYMOUS
)
def train_model_endpoint(req: func.HttpRequest) -> func.HttpResponse:
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
    models_dir = "models"
    sector_lower = sector.lower()
    sector_dir = os.path.join(models_dir, sector_lower)
    os.makedirs(sector_dir, exist_ok=True)
    
    master_file = os.path.join(sector_dir, "dataset_master.csv")
    
    df_master = pd.DataFrame()
    if os.path.exists(master_file):
        try:
            df_master = pd.read_csv(master_file)
            logging.info(f"Loaded existing master dataset with {len(df_master)} records.")
        except Exception as e:
            logging.warning(f"Could not read master dataset: {e}. Starting fresh.")
    
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
    
    # Concatenate
    if not df_master.empty:
        # Ensure master has columns (handling legacy)
        if 'Descrição_Normalizada' not in df_master.columns and 'Descrição' in df_master.columns:
             df_master['Descrição_Normalizada'] = df_master['Descrição'].map(normalize_text)
        # Add legacy tracking columns if missing
        if 'added_version' not in df_master.columns:
            df_master['added_version'] = 'legacy'
        if 'added_at' not in df_master.columns:
            df_master['added_at'] = ''
             
        df_combined = pd.concat([df_master, df_new_subset], ignore_index=True)
    else:
        df_combined = df_new_subset
        
    # Deduplicate
    # Criteria: Same Normalized Description AND Same N4. 
    # If same Description but DIFFERENT N4, we might have a conflict. For now, we'll keep the NEWEST (last).
    # Ideally, we should check for consistency. 
    # Let's drop exact duplicates first.
    before_dedup = len(df_combined)
    df_combined.drop_duplicates(subset=['Descrição_Normalizada', 'N4'], keep='last', inplace=True)
    
    # OPTIONAL: Handle conflicts (Same Description, Different N4). 
    # Current behavior: Keep both variants if N4 is different? 
    # Or assume the latest upload corrects the old one?
    # Let's assume the latest upload is the "correction" and drop duplicates on Description only, keeping last.
    # df_combined.drop_duplicates(subset=['Descrição_Normalizada'], keep='last', inplace=True)
    # Re-thinking: Sometimes arguably similar items HAVE different classes. 
    # Safest approach for now is to just deduplicate exact (Desc, N4) pairs.
    
    after_dedup = len(df_combined)
    logging.info(f"Merged data: {before_dedup} -> {after_dedup} unique items (Added {after_dedup - len(df_master)} new items).")
    
    # Save updated master
    try:
        df_combined.to_csv(master_file, index=False)
    except Exception as e:
        logging.error(f"Failed to save master dataset: {e}")
    
    df_train = df_combined
    
    if len(df_train) < 10:
        return func.HttpResponse(f"Not enough valid classified data for training (found {len(df_train)}, need 10).", status_code=400)
        
    # Import training module
    try:
        from src.model_trainer import train_model_core
        from src.ml_classifier import clear_model_cache
        
        # Train
        result = train_model_core(
            df=df_train,
            sector=sector,
            training_filename=filename
        )
        
        # Clear model cache so next classification uses the new model
        clear_model_cache(sector)
        
        # Generate Raw File (Description Only)
        # Taking the original 'Descrição' column
        df_raw = df[['Descrição']].copy()
        output_raw = io.BytesIO()
        with pd.ExcelWriter(output_raw, engine='openpyxl') as writer:
            df_raw.to_excel(writer, index=False, sheet_name='Raw')
        
        raw_b64 = base64.b64encode(output_raw.getvalue()).decode("utf-8")
        
        # Read Report
        report_path = os.path.join(result['artifacts_dir'], "training_report.txt")
        if os.path.exists(report_path):
            with open(report_path, 'r', encoding='utf-8') as f:
                report_text = f.read()
        else:
            report_text = "Report file not found."
            
        return func.HttpResponse(
            body=json.dumps({
                "status": "success",
                "message": "Model trained successfully",
                "rawFileContent": raw_b64,
                "rawFilename": f"raw_training_data_{sector}.xlsx",
                "report": report_text,
                "metrics": {
                    "accuracy": result['accuracy'],
                    "f1_macro": result['f1_macro']
                }
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
        logging.error(f"Training error: {e}")
        import traceback
        traceback.print_exc()
        return func.HttpResponse(
            f"Error during training: {str(e)}",
            status_code=500,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            }
        )

@app.function_name(name="GetModelHistory")
@app.route(
    route="GetModelHistory",
    methods=["GET", "OPTIONS"],
    auth_level=func.AuthLevel.ANONYMOUS
)
def get_model_history(req: func.HttpRequest) -> func.HttpResponse:
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
        models_dir = os.path.join(os.path.dirname(__file__), "models")
        sector_dir = os.path.join(models_dir, sector.lower())
        history_file = os.path.join(sector_dir, "model_history.json")
        
        if not os.path.exists(history_file):
            return func.HttpResponse(
                body=json.dumps([], ensure_ascii=False),
                status_code=200, 
                mimetype="application/json",
                headers={"Access-Control-Allow-Origin": "*"}
            )
            
        with open(history_file, 'r') as f:
            history = json.load(f)
            
        return func.HttpResponse(
            body=json.dumps(history, ensure_ascii=False),
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

@app.function_name(name="SetActiveModel")
@app.route(
    route="SetActiveModel",
    methods=["POST", "OPTIONS"],
    auth_level=func.AuthLevel.ANONYMOUS
)
def set_active_model(req: func.HttpRequest) -> func.HttpResponse:
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
            
        models_dir = os.path.join(os.path.dirname(__file__), "models")
        sector_dir = os.path.join(models_dir, sector.lower())
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
            body=json.dumps({"message": f"Successfully rolled back to {version_id}"}),
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

@app.function_name(name="GetModelInfo")
@app.route(
    route="GetModelInfo",
    methods=["GET", "OPTIONS"],
    auth_level=func.AuthLevel.ANONYMOUS
)
def get_model_info(req: func.HttpRequest) -> func.HttpResponse:
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
        models_dir = os.path.join(os.path.dirname(__file__), "models")
        sector_dir = os.path.join(models_dir, sector.lower())
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
            body=json.dumps(response, ensure_ascii=False),
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


@app.function_name(name="GetTrainingData")
@app.route(
    route="GetTrainingData",
    methods=["GET", "OPTIONS"],
    auth_level=func.AuthLevel.ANONYMOUS
)
def get_training_data(req: func.HttpRequest) -> func.HttpResponse:
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
        
        models_dir = os.path.join(os.path.dirname(__file__), "models")
        sector_dir = os.path.join(models_dir, sector.lower())
        master_file = os.path.join(sector_dir, "dataset_master.csv")
        
        if not os.path.exists(master_file):
            return func.HttpResponse(
                body=json.dumps({"data": [], "total": 0, "page": page, "page_size": page_size}),
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
            body=json.dumps(response, ensure_ascii=False, default=str),
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


@app.function_name(name="DeleteTrainingData")
@app.route(
    route="DeleteTrainingData",
    methods=["POST", "OPTIONS"],
    auth_level=func.AuthLevel.ANONYMOUS
)
def delete_training_data(req: func.HttpRequest) -> func.HttpResponse:
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
        models_dir = os.path.join(os.path.dirname(__file__), "models")
        sector_dir = os.path.join(models_dir, sector.lower())
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