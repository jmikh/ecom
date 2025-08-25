import re
from typing import Dict, Any, List, Optional, Tuple
from openai import OpenAI
import json
import os
from dotenv import load_dotenv
from src.search.tools import SearchTools
import logging

logger = logging.getLogger(__name__)

load_dotenv()

class QueryAgent:
    def __init__(self, mock_mode=False):
        self.search_tools = SearchTools()
        self.mock_mode = mock_mode or os.getenv('MOCK_AGENT', 'false').lower() == 'true'
        
        if self.mock_mode:
            logger.warning("⚠️  MOCK MODE: Query agent will print OpenAI requests without sending them")
            self.openai_client = None
        else:
            self.openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        self.schema = None
        
    def refresh_schema(self):
        self.schema = self.search_tools.describe_schema()
        return self.schema
    
    def parse_query(self, user_query: str) -> Tuple[Dict[str, Any], str]:
        if not self.schema:
            self.refresh_schema()
        
        columns = self.schema['tables']['products']['columns']
        
        # Build field information for the prompt
        low_card_info = {}
        numeric_info = {}
        high_card_info = {}
        
        for col_name, col_data in columns.items():
            if col_data.get('is_low_cardinality') and col_data.get('distinct_values'):
                # Show actual distinct values for low cardinality fields
                low_card_info[col_name] = {
                    'type': col_data['type'],
                    'values': col_data['distinct_values'][:20],  # Limit to first 20 for prompt
                    'total_values': len(col_data['distinct_values'])
                }
            elif col_data['type'] == 'numeric':
                numeric_info[col_name] = {
                    'type': col_data['type'],
                    'min': col_data.get('min_value'),
                    'max': col_data.get('max_value')
                }
            else:
                # High cardinality fields (text/array) that have embeddings
                high_card_info[col_name] = {
                    'type': col_data['type'],
                    'has_embeddings': col_data.get('has_embeddings', False)
                }
        
        prompt = f"""
        Parse this user query into structured filters and semantic search intent.
        
        User Query: "{user_query}"
        
        Low cardinality fields with EXACT values you can filter on:
        {json.dumps(low_card_info, indent=2)}
        
        Numeric fields (use ranges or exact values):
        {json.dumps(numeric_info, indent=2)}
        
        High cardinality fields (use for semantic search, not exact filtering):
        {json.dumps(high_card_info, indent=2)}
        
        IMPORTANT RULES:
        1. For low cardinality fields, ONLY use values from the 'values' list shown above
        2. For low cardinality fields, you can return either a single string OR an array of strings when multiple values match
        3. For numeric fields, use either a number or {{"min": X, "max": Y}}
        4. For high cardinality fields, do NOT use for exact filtering - these go to semantic_query
        5. Use simple values, not nested objects (e.g., "category": "Bracelets" or "category": ["Bracelets", "Statement bracelets"])
        
        Return a JSON object with:
        - "filters": dict of structured filters (only low-cardinality and numeric fields)
        - "semantic_query": remaining descriptive/fuzzy search terms (high-cardinality content)
        
        Examples based on available fields:
        - "bracelets under $50" -> 
          {{"filters": {{"category": ["Bracelets", "Mother daughter bracelets", "Statement bracelets"], "price": {{"max": 50}}}}, "semantic_query": ""}}
        - "statement bracelets" -> 
          {{"filters": {{"category": "Statement bracelets"}}, "semantic_query": ""}}
        - "comfortable description" -> 
          {{"filters": {{}}, "semantic_query": "comfortable description"}}
        - "silver items" ->
          {{"filters": {{}}, "semantic_query": "silver items"}}
        
        Return ONLY valid JSON.
        """
        
        model_name = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
        logger.info(f"prompt: :{prompt}")
        if self.mock_mode:
            # In mock mode, just print the request and return a mock response
            logger.info(f"🎭 MOCK MODE: OpenAI API Request")
            # Return mock response
            return {}, user_query
        
        response = self.openai_client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "You are a query parser that converts natural language to structured filters and semantic queries."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        try:
            parsed = json.loads(response.choices[0].message.content)
            filters = parsed.get('filters', {})
            semantic_query = parsed.get('semantic_query', '')
            
            # Debug logging
            logger.info(f"LLM raw response: {json.dumps(parsed, indent=2)}")
            
            cleaned_filters = {}
            for key, value in filters.items():
                if key in columns:
                    if value not in [None, "", []]:
                        cleaned_filters[key] = value
            
            logger.info(f"Cleaned filters: {cleaned_filters}")
            
            return cleaned_filters, semantic_query
        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")
            logger.error(f"Raw response: {response.choices[0].message.content}")
            return {}, user_query
    
    def search(self, user_query: str, mode: str = 'hybrid') -> Dict[str, Any]:
        filters, semantic_query = self.parse_query(user_query)
        
        results = []
        search_metadata = {
            "query": user_query,
            "parsed_filters": filters,
            "semantic_query": semantic_query,
            "mode": mode
        }
        
        if mode == 'sql' and filters:
            results = self._sql_search(filters)
        elif mode == 'semantic':
            if semantic_query or user_query:
                results = self.search_tools.semantic_search(
                    semantic_query or user_query,
                    filters=filters
                )
        else:
            if filters or semantic_query:
                results = self.search_tools.hybrid_search(
                    semantic_query or user_query,
                    filters=filters
                )
            else:
                results = self.search_tools.semantic_search(user_query)
        
        formatted_results = self._format_results(results)
        
        # Final LLM filtering: take top 5, ask LLM to return best 3 or fewer
        if formatted_results:
            logger.info(f"Search funnel - Pre-LLM filtering: {len(formatted_results)} results")
            
            # Log the top 5 results that will go to LLM filtering
            top_5 = formatted_results[:5]
            logger.info("Search funnel - Top 5 results before LLM filtering:")
            for i, result in enumerate(top_5, 1):
                logger.info(f"  {i}. {result['name']} - ${result['price']} - {result.get('match_reason', '')}")
            
            final_results = self._llm_filter_results(user_query, top_5)
            logger.info(f"Search funnel - Final results after LLM filtering: {len(final_results)}")
        else:
            final_results = []
        
        return {
            "results": final_results,
            "metadata": search_metadata,
            "total_found": len(final_results)
        }
    
    def _sql_search(self, filters: Dict[str, Any]) -> List[Dict]:
        where_clauses = []
        params = []
        
        # Get column types from schema for proper array handling  
        columns_info = self.schema['tables']['products']['columns']
        
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
            where_clause = " WHERE " + " AND ".join(where_clauses)
            query = f"SELECT * FROM products {where_clause} LIMIT 20"
            results = self.search_tools.run_sql(query, tuple(params))
            for result in results:
                result['match_reason'] = f"Exact match on filters: {filters}"
            return results
        return []
    
    def _format_results(self, results: List[Dict]) -> List[Dict]:
        formatted = []
        for result in results:
            formatted_result = {
                "id": result.get("id"),
                "name": result.get("product_name"),
                "url": result.get("url"),
                "price": float(result.get("price", 0)),
                "category": result.get("category"),
                "options": result.get("options", []),
                "rating": float(result.get("review_avg_score", 0)),
                "match_reason": result.get("match_reason", ""),
                "snippet": self._get_snippet(result)
            }
            formatted.append(formatted_result)
        return formatted
    
    def _get_snippet(self, result: Dict) -> str:
        if 'matched_field' in result and result['matched_field'] != 'combined':
            field = result['matched_field']
            content = result.get(field, '')
            if isinstance(content, list):
                content = ' '.join(str(item) for item in content[:3])
            else:
                content = str(content)
            return content[:200] + "..." if len(content) > 200 else content
        
        about = result.get('about_this_mantra', '')
        if about:
            return str(about)[:200] + "..." if len(about) > 200 else about
        
        return result.get('material', '') or result.get('product_details_fit', '')[:200]
    
    def _llm_filter_results(self, user_query: str, top_results: List[Dict]) -> List[Dict]:
        logger.info(f"LLM filtering started - input: {len(top_results)} results, mock_mode: {self.mock_mode}")
        
        if not top_results or self.mock_mode:
            # In mock mode, just return top 3
            logger.info("LLM filtering - returning mock results (top 3)")
            return top_results[:3]
        
        logger.info("LLM filtering - formatting products for LLM")
        # Format products for LLM
        products_text = ""
        for i, product in enumerate(top_results, 1):
            products_text += f"Product {i}:\n"
            products_text += f"  Name: {product['name']}\n"
            products_text += f"  Price: ${product['price']}\n"
            products_text += f"  Category: {product['category']}\n"
            products_text += f"  Options: {product.get('options', [])}\n"
            products_text += f"  Rating: {product['rating']}\n"
            products_text += f"  Match Reason: {product.get('match_reason', '')}\n"
            if product.get('snippet'):
                products_text += f"  Description: {product['snippet']}\n"
            products_text += "\n"
        
        logger.info(f"LLM filtering - formatted {len(top_results)} products, total prompt length: {len(products_text)} chars")
        
        prompt = f"""
        Original user query: "{user_query}"
        
        Here are the top 5 search results:
        {products_text}
        
        Your task: Evaluate ALL 5 products and decide which ones to include in the final results. Return AT MOST 3 products (be very lenient, only exclude if you really believe the product doesn't match).
        
        Consider:
        - How well each product matches the user's intent
        - Price relevance if mentioned
        - Category/type relevance
        - Overall quality of the match
        
        Return a JSON object with an array of all 5 products, each with:
        - product_number: The product number (1-5)
        - selected: boolean (true/false)  
        - rank: integer (1-5, where 1 is best match for the query)
        - reason: short string explaining your decision
        
        Format:
        {{
          "evaluations": [
            {{"product_number": 1, "selected": true, "rank": 1, "reason": "Perfect match - silver bracelet in budget"}},
            {{"product_number": 2, "selected": false, "rank": 4, "reason": "Wrong category - necklace not bracelet"}},
            {{"product_number": 3, "selected": true, "rank": 2, "reason": "Good alternative - rose gold bracelet"}},
            {{"product_number": 4, "selected": false, "rank": 5, "reason": "Too expensive - over budget"}},
            {{"product_number": 5, "selected": true, "rank": 3, "reason": "Excellent value - silver and affordable"}}
          ]
        }}
        
        Return ONLY valid JSON.
        """
        
        try:
            model_name = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
            logger.info(f"LLM filtering - making API call to {model_name}")
            
            # Build request parameters
            request_params = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": "You are a product search quality filter. Select only the most relevant products."},
                    {"role": "user", "content": prompt}
                ],
                "response_format": {"type": "json_object"},
            }
            
            logger.info("LLM filtering - sending request to OpenAI API")
            response = self.openai_client.chat.completions.create(**request_params)
            logger.info("LLM filtering - received response from OpenAI API")
            
            # Parse LLM response
            content = response.choices[0].message.content.strip()
            logger.info(f"LLM filtering - received content (length: {len(content)} chars)")
            logger.info(f"LLM filtering - raw response: {content}")
            
            # Parse the new detailed evaluation format
            try:
                logger.info("LLM filtering - parsing JSON response")
                parsed = json.loads(content)
                evaluations = parsed.get('evaluations', [])
                
                if not evaluations:
                    logger.warning("LLM filtering - no evaluations found in response")
                    return top_results[:3]  # Fallback
                
                logger.info(f"LLM filtering - received {len(evaluations)} evaluations")
                
                # Log all evaluations
                logger.info("LLM filtering - detailed evaluations:")
                for eval_item in evaluations:
                    product_num = eval_item.get('product_number', '?')
                    selected = eval_item.get('selected', False)
                    rank = eval_item.get('rank', '?')
                    reason = eval_item.get('reason', 'No reason given')
                    status = "✓ SELECTED" if selected else "✗ REJECTED"
                    logger.info(f"  Product {product_num}: {status} (Rank {rank}) - {reason}")
                
                # Filter and sort results based on selections and LLM ranking
                selected_items = []
                for eval_item in evaluations:
                    if eval_item.get('selected', False):
                        product_num = eval_item.get('product_number')
                        rank = eval_item.get('rank', 999)  # Default high rank if missing
                        if product_num and 1 <= product_num <= len(top_results):
                            idx = product_num - 1  # Convert to 0-based index
                            selected_items.append({
                                'product': top_results[idx],
                                'rank': rank,
                                'product_num': product_num
                            })
                            logger.debug(f"LLM filtering - included product {product_num} with rank {rank}")
                
                # Sort by LLM rank (lower rank = better)
                selected_items.sort(key=lambda x: x['rank'])
                filtered_results = [item['product'] for item in selected_items]
                
                logger.info(f"LLM filtered {len(top_results)} results down to {len(filtered_results)}")
                return filtered_results
                
            except json.JSONDecodeError as e:
                logger.warning(f"Could not parse LLM filter response: {content}")
                logger.warning(f"JSON decode error: {e}")
                return top_results[:3]  # Fallback to top 3
                
        except Exception as e:
            logger.error(f"LLM filtering failed: {e}")
            return top_results[:3]  # Fallback to top 3
    
    def explain_search(self, user_query: str) -> str:
        filters, semantic_query = self.parse_query(user_query)
        
        explanation = f"Query Analysis for: '{user_query}'\n\n"
        
        if filters:
            explanation += "Structured Filters (Exact Matches):\n"
            for key, value in filters.items():
                col_info = self.schema['tables']['products']['columns'].get(key, {})
                if isinstance(value, dict):
                    explanation += f"  - {key}: {value} (numeric range)\n"
                else:
                    explanation += f"  - {key}: {value} (cardinality: {col_info.get('cardinality', 'N/A')})\n"
        
        if semantic_query:
            explanation += f"\nSemantic Search Terms: '{semantic_query}'\n"
            explanation += "Will search in fields with embeddings:\n"
            for field in self.schema['summary']['embedding_fields']:
                explanation += f"  - {field}\n"
        
        if not filters and not semantic_query:
            explanation += "No specific filters detected - will perform general semantic search.\n"
        
        return explanation
    
    def close(self):
        self.search_tools.close()