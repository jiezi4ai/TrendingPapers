import json
import sqlite3
import pandas as pd
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
        - Automatically create table if not exist.
    """
    conn = sqlite_connect(db_name)
    if conn:
        df_converted = df.copy()

        try:
            # Check if the table exists
            cursor = conn.cursor()
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
            table_exists = cursor.fetchone() is not None

            # Create table if it doesn't exist
            if not table_exists:
                # 1. Identify and Convert Dict/List-of-Dict Columns to JSON
                # This block of code must be placed before creating the table
                for col in df_converted.columns:
                    if df_converted[col].dtype == 'object':
                        df_converted[col] = df_converted[col].apply(lambda x: json.dumps(x, ensure_ascii=False) if any(isinstance(x, (dict, list)) for x in df_converted[col].dropna()) else str(x))

                create_table_from_df(conn, df_converted, table_name, id_key)

            # Get the list of columns in the existing table
            cursor.execute(f"PRAGMA table_info({table_name})")
            table_columns = {row[1] for row in cursor.fetchall()} # Using a set for faster lookup

            if id_key and table_exists:
                # Fetch existing IDs from the database
                cursor.execute(f"SELECT DISTINCT {id_key} FROM {table_name}")
                existing_ids = {row[0] for row in cursor.fetchall()}

                # Filter out rows with IDs that already exist
                df_converted = df_converted[~df_converted[id_key].isin(existing_ids)]

            if df_converted.empty and table_exists:
                print(f"No new records to insert into '{table_name}' (based on '{id_key}').")
                return
            
            # --- Modification: Keep only relevant columns ---
            if table_exists:
                df_converted = df_converted.loc[:, df_converted.columns.isin(table_columns)]

            # Add missing columns to the DataFrame and set values to None
            if table_exists:
                for col in table_columns:
                    if col not in df_converted.columns:
                        df_converted[col] = None

            # Reorder DataFrame columns to match the table's column order
            # Convert table_columns set back to a list for ordering
            if table_exists:
                df_converted = df_converted[list(table_columns)]
            
            # 2. Explicitly define SQLite types if needed
            dtype_mapping = {}
            for col_name, col_type in df_converted.dtypes.items():
                if col_name == id_key:
                    dtype_mapping[col_name] = "TEXT PRIMARY KEY"  # Assuming ID key is text
                elif 'int' in str(col_type):
                    dtype_mapping[col_name]  = "INTEGER"
                elif 'float' in str(col_type):
                    dtype_mapping[col_name]  = "REAL"
                else:
                    dtype_mapping[col_name]  = "TEXT"

            df_converted.to_sql(
                table_name, conn, if_exists=if_exists, index=False,
                dtype=dtype_mapping
                )
            # df_converted.to_sql(table_name, conn, if_exists=if_exists, index=False)
            print(f"Data successfully written to table '{table_name}' in '{db_name}'")
        except Exception as e:
            logger.error(f"Error writing to database: {e}")
            print(f"Error writing to database: {e}")
        finally:
            conn.close()

def create_table_from_df(conn, df, table_name, id_key):
    """Creates a table in the SQLite database based on the DataFrame structure."""
    columns_sql = []
    for col_name, col_type in df.dtypes.items():
        if col_name == id_key:
            sql_type = "TEXT PRIMARY KEY"  # Assuming ID key is text
        elif 'int' in str(col_type):
            sql_type = "INTEGER"
        elif 'float' in str(col_type):
            sql_type = "REAL"
        else:
            sql_type = "TEXT"
        columns_sql.append(f'"{col_name}" {sql_type}') # Wrapping column names in double quotes

    create_table_sql = f"CREATE TABLE {table_name} ({', '.join(columns_sql)})"
    cursor = conn.cursor()
    cursor.execute(create_table_sql)
    conn.commit()
    print(f"Table '{table_name}' created successfully.")