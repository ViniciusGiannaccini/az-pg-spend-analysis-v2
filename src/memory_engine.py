import pandas as pd
import json
import os
import logging
from datetime import datetime

MEMORY_FILE = "memory_padrao.json"

class MemoryEngine:
    def __init__(self, memory_path=MEMORY_FILE):
        self.memory_path = memory_path
        self._ensure_memory_file()

    def _ensure_memory_file(self):
        if not os.path.exists(self.memory_path):
            with open(self.memory_path, 'w', encoding='utf-8') as f:
                json.dump([], f)

    def ingest(self, file_path):
        """
        Reads an Excel file and learns the classification rules.
        """
        try:
            df = pd.read_excel(file_path)
            
            # Normalize column names
            df.columns = [c.strip() for c in df.columns]
            
            # Check for required columns (flexible mapping)
            req_cols = ['Descrição', 'N1', 'N2', 'N3', 'N4']
            
            # Allow fallback for Descrição
            if 'Descrição' not in df.columns:
                if 'Item_Description' in df.columns:
                    df.rename(columns={'Item_Description': 'Descrição'}, inplace=True)
                elif 'Description' in df.columns:
                    df.rename(columns={'Description': 'Descrição'}, inplace=True)
            
            missing = [c for c in req_cols if c not in df.columns]
            if missing:
                raise ValueError(f"Colunas obrigatórias faltando: {missing}")

            new_rules = []
            current_date = datetime.now().strftime("%Y-%m-%d")

            import uuid

            for _, row in df.iterrows():
                # Only learn if N1 is filled (valid classification)
                if pd.notna(row['N1']) and str(row['N1']).strip() != "":
                    rule = {
                        "id": str(uuid.uuid4())[:8],
                        "description": str(row['Descrição']).strip(),
                        "classification": {
                            "N1": str(row['N1']).strip(),
                            "N2": str(row.get('N2', '')).strip(),
                            "N3": str(row.get('N3', '')).strip(),
                            "N4": str(row.get('N4', '')).strip()
                        },
                        "source": "consultant_upload",
                        "date_added": current_date
                    }
                    new_rules.append(rule)

            # Load existing
            with open(self.memory_path, 'r', encoding='utf-8') as f:
                existing_memory = json.load(f)

            # Simple dedup strategy: Upsert. If description exists, update it.
            # Create a dict map for existing (key by description)
            memory_map = {item['description'].lower(): item for item in existing_memory}
            
            count_new = 0
            count_updated = 0
            
            for rule in new_rules:
                key = rule['description'].lower()
                if key in memory_map:
                    # Keep existing ID if updating
                    rule['id'] = memory_map[key].get('id', rule['id']) 
                    memory_map[key] = rule # Update
                    count_updated += 1
                else:
                    memory_map[key] = rule # Insert
                    count_new += 1
            
            # Save back
            final_list = list(memory_map.values())
            
            with open(self.memory_path, 'w', encoding='utf-8') as f:
                json.dump(final_list, f, ensure_ascii=False, indent=2)
                
            logging.info(f"Memory Ingested: {count_new} new, {count_updated} updated. Total: {len(final_list)}")
            
            return {
                "success": True, 
                "message": f"{count_new + count_updated} regras aprendidas com sucesso! ({count_new} novas, {count_updated} atualizadas)",
                "total_rules": len(final_list)
            }

        except Exception as e:
            logging.error(f"Error ingesting memory: {e}")
            return {"success": False, "message": str(e)}

    def get_all(self):
        """Returns all rules."""
        with open(self.memory_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def search(self, query):
        """
        Basic case-insensitive search in descriptions.
        """
        all_rules = self.get_all()
        if not query:
            return all_rules
            
        q = query.lower()
        results = [
            r for r in all_rules 
            if q in r['description'].lower() or q in r['classification']['N1'].lower()
        ]
        return results

    def delete_rule(self, rule_id):
        """Deletes a rule by ID."""
        all_rules = self.get_all()
        initial_count = len(all_rules)
        filtered_rules = [r for r in all_rules if r.get('id') != rule_id]
        
        if len(filtered_rules) < initial_count:
            with open(self.memory_path, 'w', encoding='utf-8') as f:
                json.dump(filtered_rules, f, ensure_ascii=False, indent=2)
            return True
        return False
