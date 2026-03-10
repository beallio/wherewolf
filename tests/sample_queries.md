# Wherewolf Sample Test Queries

Use these queries in the **SQL Editor** with the `tests/test_data.csv` file loaded. 
Remember to use `dataset` as the table name.

---

## ⚡ PySpark Specific Queries (Complex)

### 1. Regex: Filter names ending in 'z' or 's' (Case Insensitive)
Tests Spark's `rlike` function.
```sql
SELECT full_name, employer_name
FROM dataset
WHERE full_name RLIKE '(?i).*[zs]$'
```

### 2. Array/List: Explode Address into components
Tests Spark's `split` function (returns an array).
```sql
SELECT 
    full_name, 
    split(address, ',') as address_parts,
    split(address, ',')[0] as street,
    split(address, ',')[1] as city_part
FROM dataset
```

### 3. Aggregate: Percentile calculation
Tests Spark's `percentile_approx`.
```sql
SELECT 
    grade, 
    percentile_approx(loan_amount, 0.5) as median_loan,
    percentile_approx(loan_amount, 0.9) as p90_loan
FROM dataset
GROUP BY grade
ORDER BY grade
```

---

## 🦆 DuckDB Specific Queries (Complex)

### 1. Regex: Extracting Zip Code from Address
Tests DuckDB's `regexp_extract`.
```sql
SELECT 
    full_name, 
    address, 
    regexp_extract(address, '(\d{5})$', 1) as zip_code
FROM dataset
WHERE address IS NOT NULL
```

### 2. List Comprehension: Map-like behavior
Tests DuckDB's unique list processing.
```sql
SELECT 
    full_name,
    loan_amount,
    [x * 1.1 for x in [loan_amount]] as loan_with_buffer
FROM dataset
LIMIT 5
```

### 3. Pivot: Loan counts by Region and Grade
Tests DuckDB's `PIVOT` syntax.
```sql
PIVOT dataset
ON region
USING count(*)
GROUP BY grade
ORDER BY grade
```

---

## 🔄 Translation Test Cases

Paste these in one engine and watch the **Translated SQL** box!

### Spark to DuckDB (Window + Filter)
```sql
SELECT * FROM (
  SELECT 
    full_name, 
    region, 
    loan_amount,
    ROW_NUMBER() OVER (PARTITION BY region ORDER BY loan_amount DESC) as rank
  FROM dataset
) WHERE rank <= 3
```

### DuckDB to Spark (Epoch conversion)
```sql
SELECT 
    full_name, 
    epoch(CAST(application_date AS TIMESTAMP)) as unix_ts
FROM dataset
```
