import psycopg2
from psycopg2.extras import RealDictCursor
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
import os
from dotenv import load_dotenv
from openai import OpenAI
import json
import logging

logger = logging.getLogger(__name__)

load_dotenv()

class SearchTools:
    def __init__(self):
        self.conn = psycopg2.connect(
            database=os.getenv('DB_NAME', 'ecom_products'),
            host=os.getenv('DB_HOST', 'localhost'),
            port=os.getenv('DB_PORT', '5432'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', ''),
            cursor_factory=RealDictCursor
        )
        self.cursor = self.conn.cursor()
        self.openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    def describe_schema(self) -> Dict[str, Any]:
        self.cursor.execute("""
            SELECT 
                column_name,
                data_type,
                is_low_cardinality,
                has_embeddings,
                distinct_values,
                cardinality,
                min_value,
                max_value
            FROM metadata
            ORDER BY column_name
        """)
        
        metadata = self.cursor.fetchall()
        
        schema_info = {
            "tables": {
                "products": {
                    "columns": {}
                }
            },
            "summary": {
                "total_products": 0,
                "indexed_fields": ["category", "price", "review_avg_score"],
                "embedding_fields": [],
                "low_cardinality_fields": []
            }
        }
        
        for row in metadata:
            col_info = {
                "type": row["data_type"],
                "cardinality": row["cardinality"],
                "is_low_cardinality": row["is_low_cardinality"],
                "has_embeddings": row["has_embeddings"]
            }
            
            if row["distinct_values"]:
                col_info["distinct_values"] = row["distinct_values"]
            
            if row["min_value"]:
                col_info["min"] = row["min_value"]
                col_info["max"] = row["max_value"]
            
            schema_info["tables"]["products"]["columns"][row["column_name"]] = col_info
            
            if row["has_embeddings"]:
                schema_info["summary"]["embedding_fields"].append(row["column_name"])
            
            if row["is_low_cardinality"] and row["distinct_values"]:
                schema_info["summary"]["low_cardinality_fields"].append(row["column_name"])
        
        schema_info["summary"]["embedding_fields"].append("combined")
        
        self.cursor.execute("SELECT COUNT(*) FROM products")
        schema_info["summary"]["total_products"] = self.cursor.fetchone()["count"]
        
        return schema_info
    
    def run_sql(self, query: str, params: Optional[tuple] = None) -> List[Dict]:
        if not query.strip().upper().startswith("SELECT"):
            raise ValueError("Only SELECT queries are allowed")
        
        forbidden_keywords = ["INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER", "TRUNCATE"]
        query_upper = query.upper()
        for keyword in forbidden_keywords:
            if keyword in query_upper:
                raise ValueError(f"Query contains forbidden keyword: {keyword}")
        
        try:
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)
            
            results = self.cursor.fetchall()
            return results[:50]
        except Exception as e:
            raise ValueError(f"SQL execution error: {str(e)}")
    
    def semantic_search(
        self,
        query: str,
        fields: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict]:
        # Default limit for semantic search results
        k = 20
        response = self.openai_client.embeddings.create(
            input=query,
            model="text-embedding-3-small",
            dimensions=1536
        )
        query_embedding = response.data[0].embedding
        
        if not fields:
            self.cursor.execute("""
                SELECT DISTINCT column_name 
                FROM metadata 
                WHERE has_embeddings = true
            """)
            fields = [row['column_name'] for row in self.cursor.fetchall()]
            fields.append('combined')
        
        where_clauses = []
        params = []
        
        # Build params in the order they appear in the SQL
        # First parameter is for similarity calculation
        params.append(query_embedding)
        
        if fields:
            field_placeholders = ','.join(['%s'] * len(fields))
            where_clauses.append(f"e.field IN ({field_placeholders})")
            params.extend(fields)
        
        if filters:
            for key, value in filters.items():
                if isinstance(value, dict):
                    if 'min' in value:
                        where_clauses.append(f"p.{key} >= %s")
                        params.append(value['min'])
                    if 'max' in value:
                        where_clauses.append(f"p.{key} <= %s")
                        params.append(value['max'])
                elif isinstance(value, list):
                    # Check if database column is array type (same logic as hybrid_search)
                    if not hasattr(self, '_schema_cache'):
                        self._schema_cache = self.describe_schema()
                    columns_info = self._schema_cache['tables']['products']['columns']
                    column_type = columns_info.get(key, {}).get('type', 'text')
                    
                    if column_type == 'array':
                        # For array columns: use overlap operator
                        placeholders = ','.join(['%s'] * len(value))
                        where_clauses.append(f"p.{key} && ARRAY[{placeholders}]")
                        params.extend(value)
                    else:
                        # For text columns: use IN clause  
                        placeholders = ','.join(['%s'] * len(value))
                        where_clauses.append(f"p.{key} IN ({placeholders})")
                        params.extend(value)
                else:
                    where_clauses.append(f"p.{key} = %s")
                    params.append(value)
        
        where_clause = " AND " + " AND ".join(where_clauses) if where_clauses else ""
        
        # Debug logging
        logger.debug(f"Semantic search where clauses: {where_clauses}")
        logger.debug(f"Semantic search params before query_embedding: {params}")
        
        query_sql = f"""
            SELECT 
                p.*,
                e.field as matched_field,
                1 - (e.embedding <=> %s::vector) as similarity_score
            FROM embeddings e
            JOIN products p ON e.product_id = p.id
            {where_clause}
            ORDER BY e.embedding <=> %s::vector
        """
        
        # Add query_embedding at the end for ORDER BY
        params.append(query_embedding)
        
        logger.debug(f"Final SQL query: {query_sql}")
        logger.debug(f"Final params: {[type(p).__name__ for p in params]}")
        
        self.cursor.execute(query_sql, params)
        results = self.cursor.fetchall()
        
        # Deduplicate by product, keeping the best score per product
        best_per_product = {}
        for result in results:
            product_id = result.get('id')
            similarity_score = result.get('similarity_score')
            
            # Skip results with invalid similarity scores
            if product_id and similarity_score is not None:
                if product_id not in best_per_product or similarity_score > best_per_product[product_id].get('similarity_score', 0):
                    result['match_reason'] = f"Semantic match in {result['matched_field']} (score: {similarity_score:.3f})"
                    best_per_product[product_id] = dict(result)
        
        # Sort by similarity score and limit to k results
        sorted_results = sorted(best_per_product.values(), key=lambda x: x.get('similarity_score', 0), reverse=True)
        return sorted_results[:k] if k else sorted_results
    
    def hybrid_search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict]:
        # Get total product count for logging
        total_products = self.describe_schema()['summary']['total_products']
        logger.info(f"Search funnel - Total products in database: {total_products}")
        sql_count = 0
        sql_where_clause = ""
        sql_params = None
        
        if filters:
            where_clauses = []
            params = []
            
            # Get column types from schema for proper array handling
            schema = self.describe_schema()
            columns_info = schema['tables']['products']['columns']
            
            for key, value in filters.items():
                if isinstance(value, dict):
                    if 'min' in value:
                        where_clauses.append(f"{key} >= %s")
                        params.append(value['min'])
                    if 'max' in value:
                        where_clauses.append(f"{key} <= %s")
                        params.append(value['max'])
                elif isinstance(value, list):
                    # Check if database column is array type
                    column_type = columns_info.get(key, {}).get('type', 'text')
                    
                    if column_type == 'array':
                        # For array columns: check if any database array elements match our filter values
                        # SQL: WHERE column && ARRAY['value1', 'value2']  (overlap operator)
                        placeholders = ','.join(['%s'] * len(value))
                        where_clauses.append(f"{key} && ARRAY[{placeholders}]")
                        params.extend(value)
                    else:
                        # For text columns: use regular IN clause
                        placeholders = ','.join(['%s'] * len(value))
                        where_clauses.append(f"{key} IN ({placeholders})")
                        params.extend(value)
                else:
                    where_clauses.append(f"{key} = %s")
                    params.append(value)
            
            if where_clauses:
                sql_where_clause = " WHERE " + " AND ".join(where_clauses)
                sql_params = tuple(params)
                
                try:
                    # First, get count for logging
                    count_query = f"SELECT COUNT(*) FROM products {sql_where_clause}"
                    count_result = self.run_sql(count_query, sql_params)
                    sql_count = count_result[0]['count'] if count_result else 0
                    logger.info(f"Search funnel - SQL filtered results: {sql_count}")
                except Exception as e:
                    logger.info(f"Search funnel - SQL filtered results: 0 (query failed: {e})")
                    sql_count = 0
        else:
            logger.info(f"Search funnel - SQL filtered results: 0 (no filters provided)")
        
        # Do semantic search with SQL prefiltering
        semantic_results = self.semantic_search(query, fields=None, filters=filters)
        for result in semantic_results:
            result['match_type'] = 'semantic'
        
        logger.info(f"Search funnel - Semantic search results: {len(semantic_results)}")
        
        # All semantic results already passed SQL filters (if any), so they all get both match types
        for idx, result in enumerate(semantic_results):
            if filters and sql_count > 0:
                # Has both SQL filter match and semantic match
                result['match_types'] = ['exact', 'semantic']
                result['match_reason'] = f"Exact filter match + Semantic similarity ({result.get('similarity_score', 0):.3f})"
                result['combined_score'] = 0.7 + (0.3 * (1.0 / (idx + 1)))  # High score for passing both
            else:
                # Only semantic match (no filters applied)  
                result['match_types'] = ['semantic']
                result['match_reason'] = f"Semantic similarity ({result.get('similarity_score', 0):.3f})"
                result['combined_score'] = 1.0 / (idx + 1)  # Semantic ranking only
        
        # Results are already sorted by semantic relevance, and all passed SQL filters
        logger.info(f"Search funnel - Combined & ranked results: {len(semantic_results)}")
        
        return semantic_results
    
    def close(self):
        self.cursor.close()
        self.conn.close()