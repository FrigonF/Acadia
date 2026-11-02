"""CSV and Excel parsing and normalization engine."""
import io
import re
from typing import List, Dict, Any, Tuple
import pandas as pd

REQUIRED_STUDENT_COLUMNS = ["name", "apaar_id", "programme", "academic_year"]

COLUMN_MAPPING = {
    "student_name": "name",
    "student name": "name",
    "fullname": "name",
    "full_name": "name",
    "name": "name",
    
    "apaar": "apaar_id",
    "apaar id": "apaar_id",
    "apaar_id": "apaar_id",
    "apaar_number": "apaar_id",
    
    "dob": "date_of_birth",
    "date_of_birth": "date_of_birth",
    "birth_date": "date_of_birth",
    
    "gender": "gender",
    "sex": "gender",
    
    "programme": "programme",
    "course": "programme",
    "branch": "programme",
    "program": "programme",
    
    "academic_year": "academic_year",
    "academic year": "academic_year",
    "year": "academic_year",
    
    "enrollment_year": "enrollment_year",
    "admission_year": "enrollment_year",
    
    "seat_category": "seat_category",
    "category": "seat_category",
    "quota": "seat_category",
    
    "enrollment_number": "enrollment_number",
    "roll_no": "enrollment_number",
    "registration_no": "enrollment_number"
}

class IngestionEngine:
    @staticmethod
    def parse_file(file_bytes: bytes, filename: str) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Parses CSV or Excel file, normalizes column names and trims strings.
        Preserves leading zeroes in APAAR ID by treating it strictly as string.
        """
        errors = []
        df = None
        lower_name = filename.lower()
        
        try:
            if lower_name.endswith('.csv'):
                # Read strictly with dtype=str to preserve leading zeros in identifiers
                df = pd.read_csv(io.BytesIO(file_bytes), dtype=str, keep_default_na=False)
            elif lower_name.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(io.BytesIO(file_bytes), dtype=str, keep_default_na=False)
            else:
                return [], [f"Unsupported file format '{filename}'. Please upload .csv or .xlsx"]
        except Exception as e:
            return [], [f"Failed to read file: {str(e)}"]

        if df.empty:
            return [], ["Uploaded file contains no rows or data."]

        # Normalize column headers
        normalized_cols = {}
        for col in df.columns:
            clean_col = str(col).strip().lower().replace("-", "_").replace(" ", "_")
            target_col = COLUMN_MAPPING.get(clean_col, clean_col)
            normalized_cols[col] = target_col
        df = df.rename(columns=normalized_cols)

        # Check required columns
        missing_req = [req for req in REQUIRED_STUDENT_COLUMNS if req not in df.columns]
        if missing_req:
            return [], [f"File is missing required columns: {', '.join(missing_req)}. Detected headers: {list(df.columns)}"]

        records = []
        for idx, row in df.iterrows():
            row_dict = {}
            for k, v in row.items():
                if isinstance(v, str):
                    val = v.strip()
                else:
                    val = str(v).strip() if pd.notna(v) else ""
                row_dict[k] = val
            row_dict["source_row"] = idx + 2 # Accounting for 1-based index and header
            records.append(row_dict)

        return records, []

ingestion_engine = IngestionEngine()
