#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import psycopg2
from psycopg2.extras import RealDictCursor
import numpy as np
from openai import OpenAI
from dotenv import load_dotenv
import json
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

load_dotenv()

class SimilarityTester:
    def __init__(self, mock_mode=False):
        # Database connection
        self.conn = psycopg2.connect(
            database=os.getenv('DB_NAME', 'ecom_products'),
            host=os.getenv('DB_HOST', 'localhost'),
            port=os.getenv('DB_PORT', '5432'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', '')
        )
        self.cursor = self.conn.cursor(cursor_factory=RealDictCursor)
        
        # OpenAI client
        self.mock_mode = mock_mode
        if not mock_mode:
            self.openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        else:
            self.openai_client = None
            print("🎭 MOCK MODE: Using zero vectors for embeddings")

    def get_query_embedding(self, query_text: str):
        """Get embedding for the query text"""
        if self.mock_mode:
            # Return zero vector for mock mode
            return [0.0] * 1536
        
        response = self.openai_client.embeddings.create(
            input=[query_text],
            model="text-embedding-3-small",
            dimensions=1536
        )
        return response.data[0].embedding

    def cosine_similarity(self, vec1, vec2):
        """Calculate cosine similarity between two vectors"""
        vec1 = np.array(vec1)
        vec2 = np.array(vec2)
        
        dot_product = np.dot(vec1, vec2)
        norm_vec1 = np.linalg.norm(vec1)
        norm_vec2 = np.linalg.norm(vec2)
        
        if norm_vec1 == 0 or norm_vec2 == 0:
            return 0.0
        
        return dot_product / (norm_vec1 * norm_vec2)

    def test_similarity(self, query_text: str, field: str = None, limit: int = 20, min_score: float = 0.0):
        """
        Test semantic similarity for a query against all products
        
        Args:
            query_text: The search query
            field: Specific field to search ('combined', 'product_name', 'options', etc.) or None for all
            limit: Max results to return
            min_score: Minimum similarity score to include
        """
        print(f"\n{'='*60}")
        print(f"SEMANTIC SIMILARITY TEST")
        print(f"{'='*60}")
        print(f"Query: '{query_text}'")
        print(f"Field: {field or 'all fields'}")
        print(f"Min Score: {min_score}")
        print(f"Limit: {limit}")
        
        # Get query embedding
        print("\n🔄 Getting query embedding...")
        query_embedding = self.get_query_embedding(query_text)
        
        # Get all embeddings from database
        if field:
            where_clause = f"WHERE field = %s"
            params = (field,)
        else:
            where_clause = ""
            params = ()
            
        query = f"""
            SELECT 
                e.product_id, 
                e.field, 
                e.embedding,
                p.product_name,
                p.price,
                p.category,
                p.options
            FROM embeddings e 
            JOIN products p ON e.product_id = p.id 
            {where_clause}
            ORDER BY e.product_id, e.field
        """
        
        print(f"🔍 Fetching embeddings from database...")
        self.cursor.execute(query, params)
        results = self.cursor.fetchall()
        
        print(f"📊 Found {len(results)} embeddings to compare")
        
        # Calculate similarities
        similarities = []
        for row in results:
            embedding = row['embedding']
            
            # Convert embedding from string/text format to list of floats
            if isinstance(embedding, str):
                # Handle PostgreSQL vector format like '[0.1, 0.2, 0.3]'
                embedding = embedding.strip('[]')
                embedding = [float(x.strip()) for x in embedding.split(',')]
            elif hasattr(embedding, 'tolist'):
                # Handle numpy array
                embedding = embedding.tolist()
            
            similarity = self.cosine_similarity(query_embedding, embedding)
            
            if similarity >= min_score:
                similarities.append({
                    'product_id': row['product_id'],
                    'field': row['field'],
                    'similarity': similarity,
                    'product_name': row['product_name'],
                    'price': row['price'],
                    'category': row['category'],
                    'options': row['options'] or []
                })
        
        # Sort by similarity score (highest first)
        similarities.sort(key=lambda x: x['similarity'], reverse=True)
        
        # Group by product and take best score per product
        best_per_product = {}
        for item in similarities:
            product_id = item['product_id']
            if product_id not in best_per_product or item['similarity'] > best_per_product[product_id]['similarity']:
                best_per_product[product_id] = item
        
        # Sort and limit final results
        final_results = sorted(best_per_product.values(), key=lambda x: x['similarity'], reverse=True)[:limit]
        
        print(f"\n{'='*60}")
        print(f"RESULTS ({len(final_results)} products)")
        print(f"{'='*60}")
        
        if not final_results:
            print("No results found above the minimum score threshold.")
            return []
        
        for i, result in enumerate(final_results, 1):
            print(f"\n{i}. {result['product_name']}")
            print(f"   Score: {result['similarity']:.4f}")
            print(f"   Field: {result['field']}")
            print(f"   Price: ${result['price']}")
            print(f"   Category: {result['category']}")
            if result['options']:
                print(f"   Options: {result['options']}")
        
        return final_results

    def compare_fields(self, query_text: str, product_id: int = None):
        """Compare similarity across different fields for debugging"""
        print(f"\n{'='*60}")
        print(f"FIELD COMPARISON")
        print(f"{'='*60}")
        print(f"Query: '{query_text}'")
        
        # Get query embedding
        query_embedding = self.get_query_embedding(query_text)
        
        # Get embeddings for specific product or all products
        if product_id:
            where_clause = f"WHERE e.product_id = %s"
            params = (product_id,)
            print(f"Product ID: {product_id}")
        else:
            where_clause = ""
            params = ()
            print("All products (showing best match per field)")
        
        query = f"""
            SELECT 
                e.product_id, 
                e.field, 
                e.embedding,
                p.product_name
            FROM embeddings e 
            JOIN products p ON e.product_id = p.id 
            {where_clause}
            ORDER BY e.field, e.product_id
        """
        
        self.cursor.execute(query, params)
        results = self.cursor.fetchall()
        
        # Group by field and calculate similarities
        field_results = {}
        for row in results:
            field = row['field']
            embedding = row['embedding']
            
            # Convert embedding from string/text format to list of floats
            if isinstance(embedding, str):
                # Handle PostgreSQL vector format like '[0.1, 0.2, 0.3]'
                embedding = embedding.strip('[]')
                embedding = [float(x.strip()) for x in embedding.split(',')]
            elif hasattr(embedding, 'tolist'):
                # Handle numpy array
                embedding = embedding.tolist()
            
            similarity = self.cosine_similarity(query_embedding, embedding)
            
            if field not in field_results:
                field_results[field] = []
            
            field_results[field].append({
                'product_id': row['product_id'],
                'product_name': row['product_name'],
                'similarity': similarity
            })
        
        # Show best match per field
        print(f"\n{'Field':<20} {'Best Score':<12} {'Product'}")
        print("-" * 60)
        
        for field, matches in field_results.items():
            best_match = max(matches, key=lambda x: x['similarity'])
            print(f"{field:<20} {best_match['similarity']:<12.4f} {best_match['product_name'][:30]}")

    def close(self):
        self.cursor.close()
        self.conn.close()

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print(f"  python {sys.argv[0]} \"search query\"")
        print(f"  python {sys.argv[0]} \"search query\" --field product_name")
        print(f"  python {sys.argv[0]} \"search query\" --limit 10 --min-score 0.7")
        print(f"  python {sys.argv[0]} \"search query\" --compare-fields")
        print(f"  python {sys.argv[0]} \"search query\" --product-id 42")
        print(f"  python {sys.argv[0]} \"search query\" --mock")
        print("\nAvailable fields: combined, product_name, options, about_this_mantra, reviews")
        sys.exit(1)
    
    # Parse arguments
    query = sys.argv[1]
    mock_mode = '--mock' in sys.argv
    field = None
    limit = 20
    min_score = 0.0
    compare_fields = '--compare-fields' in sys.argv
    product_id = None
    
    # Parse optional arguments
    for i, arg in enumerate(sys.argv):
        if arg == '--field' and i + 1 < len(sys.argv):
            field = sys.argv[i + 1]
        elif arg == '--limit' and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])
        elif arg == '--min-score' and i + 1 < len(sys.argv):
            min_score = float(sys.argv[i + 1])
        elif arg == '--product-id' and i + 1 < len(sys.argv):
            product_id = int(sys.argv[i + 1])
    
    tester = SimilarityTester(mock_mode=mock_mode)
    
    try:
        if compare_fields:
            tester.compare_fields(query, product_id)
        else:
            results = tester.test_similarity(query, field, limit, min_score)
            
            print(f"\n{'='*60}")
            print("SUMMARY")
            print(f"{'='*60}")
            print(f"Query: '{query}'")
            print(f"Results: {len(results)}")
            if results:
                print(f"Best score: {results[0]['similarity']:.4f}")
                print(f"Worst score: {results[-1]['similarity']:.4f}")
    finally:
        tester.close()

if __name__ == "__main__":
    main()