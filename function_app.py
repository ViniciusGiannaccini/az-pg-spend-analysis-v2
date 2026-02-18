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
import time
from datetime import datetime, timedelta
import uuid
import requests

# Power Automate Flow URL for saving classified files to SharePoint
POWER_AUTOMATE_URL = os.getenv("POWER_AUTOMATE_URL", "")
POWER_AUTOMATE_API_KEY = os.getenv("POWER_AUTOMATE_API_KEY", "")


# Models directory:
#   Azure: /mount/models (Azure File Share mounted at /mount)
#   Local: ./models (relative to project root)
# Override with MODELS_DIR_PATH env var if needed.
def get_models_dir() -> str:
    """Get the appropriate models directory based on environment."""
    # Allow explicit override via environment variable
    override = os.getenv("MODELS_DIR_PATH")
    if override:
        os.makedirs(override, exist_ok=True)
        return override

    # Detect Azure environment using multiple signals (Flex Consumption may not set all)
    is_azure = any(os.getenv(v) for v in [
        "WEBSITE_INSTANCE_ID", "WEBSITE_SITE_NAME", "FUNCTIONS_WORKER_RUNTIME"
    ])

    if is_azure:
        azure_models = "/mount/models"
        try:
            os.makedirs(azure_models, exist_ok=True)

            # BOOTSTRAP: Copy packaged models to writable mount on first run
            package_models = os.path.join(os.getcwd(), "models")
            if os.path.exists(package_models) and not os.listdir(azure_models):
                logging.info(f"[BOOTSTRAP] Initializing models from {package_models} to {azure_models}...")
                shutil.copytree(package_models, azure_models, dirs_exist_ok=True)
                logging.info("[BOOTSTRAP] Models copied successfully.")
            elif not os.path.exists(package_models):
                logging.warning(f"[BOOTSTRAP] Source models not found at {package_models}. Starting empty.")

        except Exception as e:
            logging.error(f"[BOOTSTRAP] Error initializing models directory: {e}")
        return azure_models

    # Local development
    return os.path.join(os.getcwd(), "models")

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
    logging.warning("ProcessTaxonomy endpoint is deprecated. Use SubmitTaxonomyJob.")
    return func.HttpResponse(
        "This endpoint is deprecated. Use SubmitTaxonomyJob.",
        status_code=410,
        mimetype="text/plain"
    )



# ---------------------------------------------------------------------------
# ASYNC TAXONOMY PROCESSING (File-Based Queue)
# ---------------------------------------------------------------------------

@app.route(
    route="SubmitTaxonomyJob",
    methods=["POST", "OPTIONS"],
    auth_level=func.AuthLevel.ANONYMOUS
)
def SubmitTaxonomyJob(req: func.HttpRequest) -> func.HttpResponse:
    """
    Accepts file upload, splits into chunks, and queues for async processing.
    Returns: jobId.
    """
    import pandas as pd
    import math
    
    # Handle CORS
    if req.method == "OPTIONS":
        return func.HttpResponse(
            status_code=200,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            }
        )
        
    logging.info('SubmitTaxonomyJob HTTP trigger function processed a request.')
    
    try:
        req_body = req.get_json()
    except ValueError:
        return func.HttpResponse("Invalid JSON body", status_code=400)
        
    file_content_b64 = req_body.get("fileContent")
    sector_raw = req_body.get("sector")
    if not file_content_b64 or not sector_raw:
        return func.HttpResponse("Missing fileContent or sector", status_code=400)
        
    sector = sector_raw.strip().capitalize()
    session_id = str(uuid.uuid4())
    
    # Create Job Directory: {MODELS_DIR}/taxonomy_jobs/{session_id}/
    job_dir = os.path.join(MODELS_DIR, "taxonomy_jobs", session_id)
    os.makedirs(job_dir, exist_ok=True)
    logging.info(f"[Submit] Job {session_id} created at {job_dir} (MODELS_DIR={MODELS_DIR})")
    
    try:
        # Decode and Load File
        file_bytes = base64.b64decode(file_content_b64)
        try:
            df = pd.read_excel(io.BytesIO(file_bytes))
        except:
             try:
                df = pd.read_csv(io.BytesIO(file_bytes), sep=';', encoding='utf-8', on_bad_lines='skip')
             except:
                df = pd.read_csv(io.BytesIO(file_bytes), sep=',', encoding='utf-8', on_bad_lines='skip')

        # Identify Description Column (Reusing Logic)
        valid_cols = [c for c in df.columns if not str(c).startswith("Unnamed")]
        if len(valid_cols) < 2:
            return func.HttpResponse("Invalid file columns.", status_code=400)
        desc_col = valid_cols[1] # Heuristic
        
        # Save Metadata
        metadata = {
            "job_id": session_id,
            "created_at": datetime.utcnow().isoformat(),
            "status": "PENDING",
            "sector": sector,
            "filename": req_body.get("originalFilename", "upload.xlsx"),
            "desc_column": desc_col,
            "total_rows": len(df),
            "client_context": req_body.get("clientContext", ""),
            "custom_hierarchy_b64": req_body.get("customHierarchy"),
            "dictionary_content_b64": req_body.get("dictionaryContent")
        }
        
        # Chunking Strategy (e.g., 500 rows per chunk)
        CHUNK_SIZE = 500
        num_chunks = math.ceil(len(df) / CHUNK_SIZE)
        metadata["total_chunks"] = num_chunks
        metadata["processed_chunks"] = 0
        
        # Save Chunks
        for i in range(num_chunks):
            chunk_df = df.iloc[i*CHUNK_SIZE : (i+1)*CHUNK_SIZE]
            chunk_path = os.path.join(job_dir, f"chunk_{i}.json")
            chunk_df.to_json(chunk_path, orient="records")
            
        # Save Status File
        with open(os.path.join(job_dir, "status.json"), "w") as f:
            json.dump(metadata, f)
            
        return func.HttpResponse(
            body=safe_json_dumps({"jobId": session_id, "status": "PENDING", "total_chunks": num_chunks}),
            status_code=202, # Accepted
            mimetype="application/json",
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            }
        )

    except Exception as e:
        logging.error(f"SubmitJob Error: {e}")
        return func.HttpResponse(f"Internal Error: {str(e)}", status_code=500)


@app.route(
    route="GetTaxonomyJobStatus",
    methods=["GET", "OPTIONS"],
    auth_level=func.AuthLevel.ANONYMOUS
)
def GetTaxonomyJobStatus(req: func.HttpRequest) -> func.HttpResponse:
    """
    Polls the status of a specific job.
    Returns: status (PENDING/PROCESSING/COMPLETED/ERROR), progress %, and result if done.
    """
    if req.method == "OPTIONS":
        return func.HttpResponse(status_code=200, headers={"Access-Control-Allow-Origin": "*"})
        
    job_id = req.params.get("jobId")
    if not job_id:
        return func.HttpResponse("Missing jobId", status_code=400)
        
    job_dir = os.path.join(MODELS_DIR, "taxonomy_jobs", job_id)
    status_file = os.path.join(job_dir, "status.json")
    
    if not os.path.exists(status_file):
        return func.HttpResponse("Job not found", status_code=404)
        
    try:
        with open(status_file, "r") as f:
            status = json.load(f)
            
        # Calculate Progress
        total = status.get("total_chunks", 1)
        processed = status.get("processed_chunks", 0)
        pct = min(int((processed / total) * 100), 99) if status["status"] != "COMPLETED" else 100

        if status["status"] == "PROCESSING":
            total_rows = status.get("total_rows", total * 500)
            items_done = min(processed * 500, total_rows)
            message = f"{items_done:,} de {total_rows:,} itens processados"
        elif status["status"] == "PENDING":
            message = "Aguardando início do processamento..."
        else:
            message = status["status"]

        response = {
            "jobId": job_id,
            "status": status["status"],
            "progress_pct": pct,
            "message": message
        }
        
        if status["status"] == "COMPLETED":
            # Load Final Result
            result_file = os.path.join(job_dir, "result.json")
            if os.path.exists(result_file):
                with open(result_file, "r") as rf:
                    response.update(json.load(rf))
            else:
                response["status"] = "ERROR"
                response["message"] = "Result file missing."

        return func.HttpResponse(
            body=safe_json_dumps(response),
            status_code=200,
            mimetype="application/json",
            headers={"Access-Control-Allow-Origin": "*"}
        )
            
    except Exception as e:
        return func.HttpResponse(f"Error reading status: {e}", status_code=500)


# ---------------------------------------------------------------------------
# WORKER HELPERS
# ---------------------------------------------------------------------------

def _cleanup_stale_jobs(jobs_root: str) -> None:
    """Marca jobs PROCESSING há mais de 1 hora como ERROR (auto-limpeza)."""
    STALE_THRESHOLD_SECONDS = 3600  # 1 hora
    for job_id in os.listdir(jobs_root):
        job_dir = os.path.join(jobs_root, job_id)
        status_path = os.path.join(job_dir, "status.json")
        if not os.path.isdir(job_dir) or not os.path.exists(status_path):
            continue
        try:
            with open(status_path, "r") as f:
                status = json.load(f)
            if status.get("status") != "PROCESSING":
                continue
            created_at = status.get("created_at")
            if not created_at:
                continue
            created_dt = datetime.fromisoformat(created_at)
            elapsed = (datetime.utcnow() - created_dt).total_seconds()
            if elapsed > STALE_THRESHOLD_SECONDS:
                logging.warning(f"[Worker] Job {job_id} travado há {elapsed/60:.0f}min. Marcando como ERROR.")
                status["status"] = "ERROR"
                status["error"] = f"Job expirou após {elapsed/60:.0f} minutos sem completar"
                with open(status_path, "w") as f:
                    json.dump(status, f)
        except Exception as e:
            logging.error(f"[Worker] Erro ao verificar job travado {job_id}: {e}")


def _get_active_jobs(jobs_root: str) -> list:
    """Coleta jobs ativos (PENDING/PROCESSING), marca PENDING como PROCESSING,
    e parseia custom_hierarchy UMA VEZ por job (evita decodificar base64+Excel a cada chunk)."""
    active = []
    for job_id in os.listdir(jobs_root):
        job_dir = os.path.join(jobs_root, job_id)
        status_path = os.path.join(job_dir, "status.json")
        if not os.path.isdir(job_dir) or not os.path.exists(status_path):
            continue
        try:
            with open(status_path, "r") as f:
                status = json.load(f)
            if status.get("status") in ["COMPLETED", "ERROR"]:
                continue
            if status["status"] == "PENDING":
                status["status"] = "PROCESSING"
                with open(status_path, "w") as f:
                    json.dump(status, f)
            # Parsear hierarquia uma vez por job
            custom_hierarchy = _parse_custom_hierarchy(status)
            hierarchy_lookup = None
            if custom_hierarchy:
                from src.hierarchy_validator import HierarchyLookup
                hierarchy_lookup = HierarchyLookup(custom_hierarchy)
            active.append({
                "job_id": job_id,
                "job_dir": job_dir,
                "status_path": status_path,
                "status": status,
                "total_chunks": status["total_chunks"],
                "custom_hierarchy": custom_hierarchy,
                "hierarchy_lookup": hierarchy_lookup,
            })
        except Exception as e:
            logging.error(f"[Worker] Erro ao ler job {job_id}: {e}")
    return active


def _find_next_chunk(job_info: dict):
    """Retorna o índice do próximo chunk não processado, ou None se todos prontos."""
    job_dir = job_info["job_dir"]
    for i in range(job_info["total_chunks"]):
        chunk_file = os.path.join(job_dir, f"chunk_{i}.json")
        result_file = os.path.join(job_dir, f"result_{i}.json")
        if os.path.exists(chunk_file) and not os.path.exists(result_file):
            return i
    return None


def _find_next_chunks(job_info: dict, max_count: int = 1, exclude: set = None) -> list:
    """Retorna até max_count índices de chunks não processados (excluindo já atribuídos)."""
    if exclude is None:
        exclude = set()
    job_dir = job_info["job_dir"]
    chunks = []
    for i in range(job_info["total_chunks"]):
        if len(chunks) >= max_count:
            break
        if i in exclude:
            continue
        chunk_file = os.path.join(job_dir, f"chunk_{i}.json")
        result_file = os.path.join(job_dir, f"result_{i}.json")
        if os.path.exists(chunk_file) and not os.path.exists(result_file):
            chunks.append(i)
    return chunks


def _parse_custom_hierarchy(status: dict):
    """Decodifica custom_hierarchy_b64 do status do job, se presente.
    Robusto: detecta a linha de headers (N1,N2,N3,N4) mesmo com linhas vazias antes."""
    import pandas as pd
    if not status.get("custom_hierarchy_b64"):
        return None
    try:
        cust_bytes = base64.b64decode(status["custom_hierarchy_b64"])

        # 1. Ler sem assumir posição dos headers
        df_raw = pd.read_excel(io.BytesIO(cust_bytes), header=None)

        # 2. Encontrar a linha que contém N1, N2, N3, N4
        header_row = None
        for idx, row in df_raw.iterrows():
            values = [str(v).strip().upper() for v in row.values]
            if 'N1' in values and 'N4' in values:
                header_row = idx
                break

        if header_row is None:
            logging.error("Custom hierarchy: headers N1/N4 não encontrados no arquivo")
            return None

        # 3. Re-ler com o header correto
        df_hier = pd.read_excel(io.BytesIO(cust_bytes), header=header_row)
        df_hier.columns = [str(c).strip().upper() for c in df_hier.columns]

        if 'N4' not in df_hier.columns:
            logging.error(f"Custom hierarchy: coluna N4 ausente. Colunas: {list(df_hier.columns)}")
            return None

        # 4. Construir hierarquia como LISTA (preserva N4s duplicados como "Materiais OEM" em múltiplas marcas)
        custom_hierarchy = []
        for _, row in df_hier.iterrows():
            n4 = str(row.get('N4', '')).strip()
            if n4 and n4.upper() != 'NAN':
                custom_hierarchy.append({
                    'N1': str(row.get('N1', '')).strip() if pd.notna(row.get('N1')) else '',
                    'N2': str(row.get('N2', '')).strip() if pd.notna(row.get('N2')) else '',
                    'N3': str(row.get('N3', '')).strip() if pd.notna(row.get('N3')) else '',
                    'N4': n4,
                })

        logging.info(f"Custom hierarchy parsed: {len(custom_hierarchy)} entries (list format, preserves duplicates)")
        return custom_hierarchy if custom_hierarchy else None
    except Exception as e:
        logging.error(f"Failed to parse custom hierarchy: {e}")
        return None


def _process_single_chunk(job_info: dict, chunk_index: int) -> None:
    """Processa um único chunk de um job e salva o resultado.
    NÃO atualiza status.json (chamador deve usar _update_job_progress após batch paralelo)."""
    import pandas as pd
    from src.core_classification import process_dataframe_chunk

    job_dir = job_info["job_dir"]
    status = job_info["status"]
    job_id = job_info["job_id"]
    total_chunks = job_info["total_chunks"]

    chunk_file = os.path.join(job_dir, f"chunk_{chunk_index}.json")
    result_file = os.path.join(job_dir, f"result_{chunk_index}.json")

    logging.info(f"[Worker] Processing Job {job_id} - Chunk {chunk_index}/{total_chunks}")

    df_chunk = pd.read_json(chunk_file, orient="records")

    # Usa hierarquia já parseada no _get_active_jobs (evita re-decodificar base64+Excel por chunk)
    custom_hierarchy = job_info.get("custom_hierarchy")

    results = process_dataframe_chunk(
        df_chunk=df_chunk,
        sector=status["sector"],
        desc_column=status["desc_column"],
        custom_hierarchy=custom_hierarchy,
        client_context=status.get("client_context", ""),
        hierarchy_lookup=job_info.get("hierarchy_lookup")
    )

    with open(result_file, "w") as rf:
        json.dump(results, rf)


def _update_job_progress(job_info: dict) -> None:
    """Atualiza processed_chunks no status.json. Chamar FORA de contexto paralelo."""
    job_dir = job_info["job_dir"]
    total_chunks = job_info["total_chunks"]
    processed_so_far = sum(
        1 for j in range(total_chunks)
        if os.path.exists(os.path.join(job_dir, f"result_{j}.json"))
    )
    job_info["status"]["processed_chunks"] = processed_so_far
    with open(job_info["status_path"], "w") as f:
        json.dump(job_info["status"], f)


def _consolidate_job(job_info: dict) -> None:
    """Consolida resultados de todos os chunks em Excel final e marca COMPLETED."""
    import pandas as pd
    from src.taxonomy_engine import generate_analytics, generate_summary
    import glob as glob_mod

    job_dir = job_info["job_dir"]
    status = job_info["status"]
    job_id = job_info["job_id"]
    total_chunks = job_info["total_chunks"]
    status_path = job_info["status_path"]

    logging.info(f"[Worker] Job {job_id} Completed! Consolidating...")

    # Acumular resultados de classificação
    results_accumulated = []
    for i in range(total_chunks):
        res_path = os.path.join(job_dir, f"result_{i}.json")
        if os.path.exists(res_path):
            with open(res_path, "r") as rf:
                results_accumulated.extend(json.load(rf))

    results_df = pd.DataFrame(results_accumulated)

    # Unir com dados originais (descrições + outras colunas)
    original_chunks = []
    for i in range(total_chunks):
        chunk_path = os.path.join(job_dir, f"chunk_{i}.json")
        if os.path.exists(chunk_path):
            with open(chunk_path, "r") as cf:
                original_chunks.extend(json.load(cf))

    if original_chunks and len(original_chunks) == len(results_accumulated):
        original_df = pd.DataFrame(original_chunks)
        cols_to_drop = [c for c in original_df.columns if c.startswith('_')]
        original_df.drop(columns=cols_to_drop, errors='ignore', inplace=True)
        # Remover colunas do original que colidem com resultados (evita duplicate labels)
        overlap = [c for c in original_df.columns if c in results_df.columns]
        if overlap:
            logging.info(f"[Consolidate] Dropping overlapping columns from original: {overlap}")
            original_df.drop(columns=overlap, inplace=True)
        final_df = pd.concat([original_df.reset_index(drop=True), results_df.reset_index(drop=True)], axis=1)
    else:
        final_df = results_df

    # Analytics e Summary
    analytics = generate_analytics(final_df)
    summary = generate_summary(final_df, status.get("desc_column", "Descricao"))

    # Gerar Excel
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        final_df.to_excel(writer, index=False, sheet_name='Classificação')
    output.seek(0)
    xlsx_b64 = base64.b64encode(output.getvalue()).decode("utf-8")

    final_result = {
        "items": final_df.to_dict(orient="records"),
        "analytics": analytics,
        "summary": summary,
        "fileContent": xlsx_b64,
        "filename": f"classified_{status['filename']}"
    }

    with open(os.path.join(job_dir, "result.json"), "w") as f:
        json.dump(final_result, f)

    status["status"] = "COMPLETED"
    with open(status_path, "w") as f:
        json.dump(status, f)

    # Limpar chunks e resultados intermediários
    for chunk_file in glob_mod.glob(os.path.join(job_dir, "chunk_*.json")):
        try:
            os.remove(chunk_file)
        except OSError:
            pass
    for res_chunk in glob_mod.glob(os.path.join(job_dir, "result_*.json")):
        try:
            os.remove(res_chunk)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# TIMER TRIGGER: Background Worker (Round-Robin entre jobs)
# Runs every 15 seconds to process chunks
# ---------------------------------------------------------------------------
@app.schedule(schedule="*/15 * * * * *", arg_name="myTimer", run_on_startup=False,
              use_monitor=False)
def ProcessTaxonomyWorker(myTimer: func.TimerRequest) -> None:
    if myTimer.past_due:
        logging.info('The timer is past due!')

    jobs_root = os.path.join(MODELS_DIR, "taxonomy_jobs")
    if not os.path.exists(jobs_root):
        logging.info(f"[Worker] No jobs directory at {jobs_root} (MODELS_DIR={MODELS_DIR})")
        return

    # 1. Auto-limpeza de jobs travados (PROCESSING > 1h → ERROR)
    _cleanup_stale_jobs(jobs_root)

    # 2. Coletar jobs ativos (PENDING → PROCESSING)
    active_jobs = _get_active_jobs(jobs_root)
    if not active_jobs:
        return

    logging.info(f"[Worker] {len(active_jobs)} job(s) ativo(s): {[j['job_id'][:8] for j in active_jobs]}")

    # 3. Round-robin paralelo: até MAX_PARALLEL_CHUNKS chunks simultâneos entre todos os jobs
    from concurrent.futures import ThreadPoolExecutor, as_completed

    MAX_PARALLEL_CHUNKS = 5
    MAX_PROCESSING_TIME = 20 * 60  # 20 minutos
    worker_start_time = time.time()

    while True:
        elapsed = time.time() - worker_start_time
        if elapsed > MAX_PROCESSING_TIME:
            logging.info(f"[Worker] Time budget atingido ({elapsed:.0f}s). Jobs continuam no próximo ciclo.")
            break

        # Coletar até MAX_PARALLEL_CHUNKS via round-robin justo entre jobs
        batch = []
        pending = [j for j in active_jobs if j["status"].get("status") != "ERROR"]
        assigned = {j["job_id"]: set() for j in pending}

        # Round-robin: 1 chunk por job por rodada, repetir até preencher batch
        while len(batch) < MAX_PARALLEL_CHUNKS and pending:
            next_round = []
            for job in pending:
                if len(batch) >= MAX_PARALLEL_CHUNKS:
                    break
                jid = job["job_id"]
                available = _find_next_chunks(job, max_count=1, exclude=assigned[jid])
                if available:
                    batch.append((job, available[0]))
                    assigned[jid].add(available[0])
                    next_round.append(job)
            pending = next_round

        if not batch:
            break

        logging.info(f"[Worker] Processando {len(batch)} chunk(s) em paralelo: "
                     f"{[(j['job_id'][:8], c) for j, c in batch]}")

        # Processar batch em paralelo
        with ThreadPoolExecutor(max_workers=MAX_PARALLEL_CHUNKS) as executor:
            futures = {
                executor.submit(_process_single_chunk, job, idx): (job, idx)
                for job, idx in batch
            }
            for future in as_completed(futures):
                job, idx = futures[future]
                try:
                    future.result()
                except Exception as e:
                    logging.error(f"[Worker] Erro no Job {job['job_id']} chunk {idx}: {e}")
                    job["status"]["status"] = "ERROR"
                    job["status"]["error"] = str(e)
                    with open(job["status_path"], "w") as f:
                        json.dump(job["status"], f)

        # Atualizar progresso de todos os jobs tocados (sequencial, sem race condition)
        touched = set(j["job_id"] for j, _ in batch)
        for job in active_jobs:
            if job["job_id"] in touched and job["status"].get("status") != "ERROR":
                _update_job_progress(job)

    # 4. Consolidar jobs que completaram todos os chunks
    for job_info in active_jobs:
        if job_info["status"].get("status") == "ERROR":
            continue
        all_done = all(
            os.path.exists(os.path.join(job_info["job_dir"], f"result_{i}.json"))
            for i in range(job_info["total_chunks"])
        )
        if all_done:
            try:
                _consolidate_job(job_info)
            except Exception as e:
                import traceback
                logging.error(f"[Worker] Erro ao consolidar Job {job_info['job_id']}: {e}\n{traceback.format_exc()}")
                job_info["status"]["status"] = "ERROR"
                job_info["status"]["error"] = f"Consolidation error: {e}"
                with open(job_info["status_path"], "w") as f:
                    json.dump(job_info["status"], f)

# ---------------------------------------------------------------------------


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
