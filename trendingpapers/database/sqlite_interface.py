import json
import sqlite3

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def sqlite_connect(db_name):
    try:
        conn = sqlite3.connect(db_name)
        return conn
    except sqlite3.Error as e:
        print(f"Error connecting to database: {e}")
        return None

def df_to_sqlite(
        df, 
        table_name, 
        db_name, 
        id_key=None,
        if_exists='append' 
        ):   
    """import pandas DataFrame to SQLite database
    Args:
        :param pd.DataFrame df: DataFrame to import
        :param str table_name: table name to import to
        :param str db_name: database name
        :param str id_key: primary key for the table
        :param str if_exists: 'append' or 'replace'
    Returns:
        :returns: None
    Note:
        - If 'id_key' is provided, the function will check for existing records in the database and only insert new records.
        - If 'if_exists' is set to 'replace', the function will replace the existing table with the new data.
        - If 'if_exists' is set to 'append', the function will append the new data to the existing table.
        - The code would automatically neglect columns that are not in the table.
        - The code would set the value of missing columns to None.
    """
    conn = sqlite_connect(db_name)
    if conn:
        df_converted = df.copy()

        try:
            # Get the list of columns in the existing table
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info({table_name})")
            table_columns = {row[1] for row in cursor.fetchall()} # Using a set for faster lookup

            if id_key:
                # Fetch existing IDs from the database
                cursor.execute(f"SELECT {id_key} FROM {table_name}")
                existing_ids = {row[0] for row in cursor.fetchall()}

                # Filter out rows with IDs that already exist
                df_converted = df_converted[~df_converted[id_key].isin(existing_ids)]

            if df_converted.empty:
                print(f"No new records to insert into '{table_name}' (based on '{id_key}').")
                return
            
            # --- Modification: Keep only relevant columns ---
            df_converted = df_converted.loc[:, df_converted.columns.isin(table_columns)]

            # Add missing columns to the DataFrame and set values to None
            for col in table_columns:
                if col not in df_converted.columns:
                    df_converted[col] = None

            # 1. Identify and Convert Dict/List-of-Dict Columns to JSON
            for col in df_converted.columns:
                if df_converted[col].dtype == 'object':
                    df_converted[col] = df_converted[col].apply(lambda x: json.dumps(x, ensure_ascii=False) if any(isinstance(x, (dict, list)) for x in df_converted[col].dropna()) else str(x))

            # Reorder DataFrame columns to match the table's column order
            # Convert table_columns set back to a list for ordering
            df_converted = df_converted[list(table_columns)]

            # 2. Explicitly define SQLite types if needed
            dtype_mapping = {}
            for col in df_converted.columns:
                if df_converted[col].dtype == 'object':
                    dtype_mapping[col] = 'TEXT'
                elif df_converted[col].dtype == 'int64':
                    dtype_mapping[col] = 'INTEGER'
                elif df_converted[col].dtype == 'float64':
                    dtype_mapping[col] = 'REAL'

            df_converted.to_sql(
                table_name, conn, if_exists=if_exists, index=False,
                dtype=dtype_mapping
                )
            print(f"Data successfully written to table '{table_name}' in '{db_name}'")
        except Exception as e:
            logger.error(f"Error writing to database: {e}")
            print(f"Error writing to database: {e}")
        finally:
            conn.close()