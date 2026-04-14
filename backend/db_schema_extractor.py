#!/usr/bin/env python3
"""
Database Schema Extractor for Supabase PostgreSQL
Extracts all tables, columns, relationships, and generates markdown documentation
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import json
from typing import List, Dict, Any

DATABASE_URL = "postgresql://postgres.iufvqyrwevigkvpcanvk:VLicS4lj7ysdagF9@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres"

def get_connection():
    """Create a database connection"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
        raise

def get_all_tables(conn) -> List[str]:
    """Get all user-defined tables in the database"""
    query = """
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public'
    AND table_type = 'BASE TABLE'
    ORDER BY table_name;
    """

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query)
        return [row['table_name'] for row in cur.fetchall()]

def get_table_columns(conn, table_name: str) -> List[Dict[str, Any]]:
    """Get all columns for a specific table"""
    query = """
    SELECT
        column_name,
        data_type,
        is_nullable,
        column_default,
        character_maximum_length,
        numeric_precision,
        numeric_scale
    FROM information_schema.columns
    WHERE table_schema = 'public'
    AND table_name = %s
    ORDER BY ordinal_position;
    """

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, (table_name,))
        return cur.fetchall()

def get_primary_keys(conn, table_name: str) -> List[str]:
    """Get primary key columns for a table"""
    query = """
    SELECT kcu.column_name
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu
        ON tc.constraint_name = kcu.constraint_name
        AND tc.table_schema = kcu.table_schema
    WHERE tc.constraint_type = 'PRIMARY KEY'
    AND tc.table_name = %s
    ORDER BY kcu.ordinal_position;
    """

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, (table_name,))
        return [row['column_name'] for row in cur.fetchall()]

def get_foreign_keys(conn, table_name: str) -> List[Dict[str, Any]]:
    """Get all foreign keys for a table"""
    query = """
    SELECT
        tc.constraint_name,
        kcu.column_name,
        ccu.table_name AS foreign_table_name,
        ccu.column_name AS foreign_column_name
    FROM information_schema.table_constraints AS tc
    JOIN information_schema.key_column_usage AS kcu
        ON tc.constraint_name = kcu.constraint_name
        AND tc.table_schema = kcu.table_schema
    JOIN information_schema.constraint_column_usage AS ccu
        ON ccu.constraint_name = tc.constraint_name
        AND ccu.table_schema = tc.table_schema
    WHERE tc.constraint_type = 'FOREIGN KEY'
    AND tc.table_name = %s;
    """

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, (table_name,))
        return cur.fetchall()

def get_unique_constraints(conn, table_name: str) -> List[Dict[str, Any]]:
    """Get all unique constraints for a table"""
    query = """
    SELECT
        tc.constraint_name,
        string_agg(kcu.column_name, ', ') as columns
    FROM information_schema.table_constraints AS tc
    JOIN information_schema.key_column_usage AS kcu
        ON tc.constraint_name = kcu.constraint_name
        AND tc.table_schema = kcu.table_schema
    WHERE tc.constraint_type = 'UNIQUE'
    AND tc.table_name = %s
    GROUP BY tc.constraint_name;
    """

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, (table_name,))
        return cur.fetchall()

def get_indexes(conn, table_name: str) -> List[Dict[str, Any]]:
    """Get all indexes for a table"""
    query = """
    SELECT
        indexname,
        indexdef
    FROM pg_indexes
    WHERE tablename = %s
    AND schemaname = 'public';
    """

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, (table_name,))
        return cur.fetchall()

def generate_markdown(data: Dict[str, Any]) -> str:
    """Generate markdown documentation from extracted schema"""

    markdown = """# PetCircle Supabase Database Schema

**Database:** PostgreSQL (Supabase)
**Project:** iufvqyrwevigkvpcanvk
**Generated:** Automated Schema Documentation

---

## Table of Contents

"""

    # Generate TOC
    for table_name in sorted(data['tables'].keys()):
        markdown += f"- [{table_name}](#{table_name})\n"

    markdown += "\n---\n\n"

    # Generate table details
    for table_name in sorted(data['tables'].keys()):
        table_data = data['tables'][table_name]

        markdown += f"## {table_name}\n\n"
        markdown += f"**Description:** {table_data.get('description', 'N/A')}\n\n"

        # Columns section
        markdown += "### Columns\n\n"
        markdown += "| Column | Type | Nullable | Default | Notes |\n"
        markdown += "|--------|------|----------|---------|-------|\n"

        for col in table_data['columns']:
            col_type = col['data_type']
            if col['character_maximum_length']:
                col_type += f"({col['character_maximum_length']})"
            elif col['numeric_precision']:
                col_type += f"({col['numeric_precision']},{col['numeric_scale']})"

            nullable = "Yes" if col['is_nullable'] == 'YES' else "No"
            default = col['column_default'] if col['column_default'] else "-"

            # Mark primary keys
            notes = ""
            if col['column_name'] in table_data['primary_keys']:
                notes += "[PK]"

            markdown += f"| {col['column_name']} | {col_type} | {nullable} | {default} | {notes} |\n"

        markdown += "\n"

        # Primary Keys
        if table_data['primary_keys']:
            markdown += "### Primary Key\n\n"
            markdown += f"```\n"
            markdown += f"{', '.join(table_data['primary_keys'])}\n"
            markdown += f"```\n\n"

        # Foreign Keys
        if table_data['foreign_keys']:
            markdown += "### Foreign Keys\n\n"
            for fk in table_data['foreign_keys']:
                markdown += f"- **{fk['column_name']}** → {fk['foreign_table_name']}.{fk['foreign_column_name']}\n"
            markdown += "\n"

        # Unique Constraints
        if table_data['unique_constraints']:
            markdown += "### Unique Constraints\n\n"
            for uc in table_data['unique_constraints']:
                markdown += f"- **{uc['constraint_name']}** on ({uc['columns']})\n"
            markdown += "\n"

        # Indexes
        if table_data['indexes']:
            markdown += "### Indexes\n\n"
            for idx in table_data['indexes']:
                markdown += f"- {idx['indexname']}\n"
            markdown += "\n"

        markdown += "---\n\n"

    return markdown

def main():
    """Main execution"""
    conn = None
    try:
        conn = get_connection()

        print("Extracting database schema...")

        # Get all tables
        tables = get_all_tables(conn)
        print(f"[OK] Found {len(tables)} tables")

        # Extract data for each table
        schema_data = {'tables': {}}

        for table_name in tables:
            print(f"   - Processing {table_name}...", end=" ")

            columns = get_table_columns(conn, table_name)
            primary_keys = get_primary_keys(conn, table_name)
            foreign_keys = get_foreign_keys(conn, table_name)
            unique_constraints = get_unique_constraints(conn, table_name)
            indexes = get_indexes(conn, table_name)

            schema_data['tables'][table_name] = {
                'columns': columns,
                'primary_keys': primary_keys,
                'foreign_keys': foreign_keys,
                'unique_constraints': unique_constraints,
                'indexes': indexes,
                'description': 'Auto-extracted from database'
            }

            print(f"({len(columns)} columns, {len(foreign_keys)} FKs)")

        # Generate markdown
        print("\n[INFO] Generating markdown documentation...")
        markdown = generate_markdown(schema_data)

        # Save to file
        output_file = "DATABASE_SCHEMA.md"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(markdown)

        print(f"[OK] Schema documentation saved to {output_file}")

        # Also save raw JSON for reference
        json_file = "database_schema.json"
        # Convert to JSON-serializable format
        json_data = {}
        for table_name, table_info in schema_data['tables'].items():
            json_data[table_name] = {
                'columns': [dict(col) for col in table_info['columns']],
                'primary_keys': table_info['primary_keys'],
                'foreign_keys': [dict(fk) for fk in table_info['foreign_keys']],
                'unique_constraints': [dict(uc) for uc in table_info['unique_constraints']],
                'indexes': [dict(idx) for idx in table_info['indexes']],
            }

        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, default=str)

        print(f"[OK] Raw schema data saved to {json_file}")

    except Exception as e:
        print(f"[ERROR] Error: {e}")
        raise
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    main()
