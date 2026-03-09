**Role:**  
You are an expert Python developer and Data Engineer with deep experience in **Streamlit, DuckDB, PySpark, Ibis, SQL translation (SQLGlot), and local file system tooling**. You are tasked with producing **production-grade Python code** that implements a local SQL workbench called *Wherewolf*.

---

**Project Requirements:**  

1. **UI Framework:**  
   - Use **Streamlit** as the web framework.  
   - Sidebar to select:
     - Dataset path (local filesystem).  
     - Execution engine (**DuckDB** or **Spark**).  
     - Preview size (number of rows, max 1000).  
     - Export format (CSV, Excel, Parquet).  
     - Query history selection.  
   - Main area:
     - SQL editor.  
     - “Run Query” and “Cancel Query” buttons.  
     - Scrollable preview of query results.  
     - Execution metrics (time, rows returned).  
     - Translated SQL for the other engine.  
     - Export buttons for selected format.

2. **Dataset Handling:**  
   - Users provide filesystem paths (CSV, Parquet, JSON).  
   - No dataset registration required; the path is the source.  
   - For Spark, automatically register the dataset as a temporary view before query execution.

3. **Query Execution:**  
   - Support **SQL only** (no Ibis expressions in UI).  
   - Use **Ibis** as a translation layer for backend engine execution.  
   - Execute queries via the selected engine:
     - DuckDB (local, in-process).  
     - Spark (local[*] mode).  
   - Allow **single query execution** at a time, with **cancellation support**.  
   - Limit preview to **1000 rows**, but full query results can be exported.  
   - Display **elapsed execution time** and **rows returned**.

4. **SQL Translation:**  
   - Use **SQLGlot** to translate queries between DuckDB and SparkSQL.  
   - Display the translated SQL in the UI.  
   - Warn the user if translation may be imperfect due to dialect differences.  

5. **Export:**  
   - Export query results to **CSV, Excel, or Parquet**.  
   - Use `st.download_button` for browser download.  

6. **History Storage:**  
   - Save SQL query history locally at `~/.wherewolf/history.json`.  
   - Store: timestamp, engine, query text.  
   - Load history in sidebar for selection and rerun.

7. **Error Handling:**  
   - Show simple errors by default.  
   - Option to view full traceback/details.

8. **Code Structure:**  
   - Modular:
     ```
     wherewolf/
       app.py
       ui/
       execution/
       translation/
       export/
       storage/
       models/
     ```  
   - Include clear docstrings and type hints.  
   - Threaded query execution for cancellation.  

9. **Performance Considerations:**  
   - Efficiently handle datasets larger than memory (streaming for preview if necessary).  
   - Only fetch preview rows for UI; full result only for export.  

10. **Dependencies:**  
    ```
    streamlit
    duckdb
    pyspark
    ibis-framework
    sqlglot
    pandas
    pyarrow
    openpyxl
    ```

11. **Script Header:**  
    Include **PEP 723 / UV-run compatible header**:
    ```python
    # /// script
    # requires-python = ">=3.11"
    # dependencies = [
    #   "streamlit",
    #   "duckdb",
    #   "pyspark",
    #   "ibis-framework",
    #   "sqlglot",
    #   "pandas",
    #   "pyarrow",
    #   "openpyxl"
    # ]
    # ///
    ```

---

**Output Requirements:**  

- Produce **fully runnable Python code** (`app.py`) with all modules stubbed in a modular directory structure.  
- Ensure **robust handling of SQL dialect translation**, engine execution, and export functionality.  
- Include **comments explaining design choices**.  
- Minimize assumptions about dataset schema.  
- Include **scrollable preview** in Streamlit with max 1000 rows.  
- Implement **query cancellation**, timing, and metrics display.  
- Provide **informative error handling** with optional detailed view.  
- Follow Python **best practices** for production code.  

---

**Additional Instructions:**  

- Make the UI **responsive and user-friendly**.  
- Default dataset preview and export functionality must work out-of-the-box for CSV/Parquet.  
- Modularize all components for **future extensibility** (e.g., adding new engines).  
- Include **sample code for engine initialization** (DuckDB connection, SparkSession).  
- Do **not include notebook-style cells**; produce a production-ready **script/application**.

---

**Goal:**  

Produce a **production-grade, local Streamlit webapp** that allows a user to:

1. Execute SQL queries against DuckDB or Spark datasets.  
2. Translate the SQL to the alternative engine.  
3. Preview results safely in a scrollable table.  
4. Export results in multiple formats.  
5. Persist query history locally for future sessions.  
6. Monitor execution metrics and handle errors gracefully.

