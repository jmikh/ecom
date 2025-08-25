#!/usr/bin/env python3
"""
Fetch all products with variants from Shopify store
"""

import os
import json
import time
from typing import List, Dict, Any, Optional
import requests
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()


class ShopifyProductFetcher:
    def __init__(self):
        """Initialize Shopify API client"""
        self.shop_url = os.getenv('SHOPIFY_SHOP_URL', '').rstrip('/')
        self.access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
        self.api_version = os.getenv('SHOPIFY_API_VERSION', '2024-01')
        
        if not self.shop_url or not self.access_token:
            raise ValueError("SHOPIFY_SHOP_URL and SHOPIFY_ACCESS_TOKEN must be set in .env")
        
        # Build base URL for API calls
        self.base_url = f"{self.shop_url}/admin/api/{self.api_version}"
        
        # Set up headers
        self.headers = {
            'X-Shopify-Access-Token': self.access_token,
            'Content-Type': 'application/json'
        }
        
        # Rate limiting: Shopify allows 2 requests per second for most APIs
        self.rate_limit_delay = 0.5  # 500ms between requests
        
    def fetch_products(self, limit: int = 250) -> List[Dict[str, Any]]:
        """
        Fetch all products from Shopify with pagination
        
        Args:
            limit: Number of products per page (max 250)
            
        Returns:
            List of all products with their variants
        """
        all_products = []
        endpoint = f"{self.base_url}/products.json"
        
        params = {
            'limit': min(limit, 250),  # Shopify max is 250
            'fields': 'id,title,handle,body_html,vendor,product_type,created_at,updated_at,published_at,tags,status,variants,images,options'
        }
        
        page_info = None
        page_count = 0
        
        while True:
            # Use page_info for pagination after first request
            if page_info:
                params = {'page_info': page_info, 'limit': params['limit']}
            
            try:
                response = requests.get(endpoint, headers=self.headers, params=params)
                response.raise_for_status()
                
                data = response.json()
                products = data.get('products', [])
                
                if not products:
                    break
                
                all_products.extend(products)
                page_count += 1
                
                print(f"Fetched page {page_count}: {len(products)} products (Total: {len(all_products)})")
                
                # Check for next page
                link_header = response.headers.get('Link', '')
                page_info = self._extract_page_info(link_header, 'next')
                
                if not page_info:
                    break
                
                # Rate limiting
                time.sleep(self.rate_limit_delay)
                
            except requests.exceptions.RequestException as e:
                print(f"Error fetching products: {e}")
                if hasattr(e.response, 'text'):
                    print(f"Response: {e.response.text}")
                break
        
        return all_products
    
    def _extract_page_info(self, link_header: str, rel: str) -> Optional[str]:
        """
        Extract page_info from Link header
        
        Args:
            link_header: The Link header from response
            rel: The relationship type ('next' or 'previous')
            
        Returns:
            page_info value or None
        """
        if not link_header:
            return None
        
        links = link_header.split(',')
        for link in links:
            if f'rel="{rel}"' in link:
                # Extract URL from <url>
                url_match = link.split(';')[0].strip().strip('<>')
                # Extract page_info parameter
                if 'page_info=' in url_match:
                    page_info = url_match.split('page_info=')[1].split('&')[0]
                    return page_info
        
        return None
    
    def transform_products(self, products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Transform Shopify products to a cleaner format
        
        Args:
            products: Raw products from Shopify API
            
        Returns:
            Transformed products with flattened variants
        """
        transformed = []
        
        for product in products:
            base_product = {
                'product_id': product['id'],
                'title': product['title'],
                'handle': product['handle'],
                'description': product.get('body_html', ''),
                'vendor': product.get('vendor'),
                'product_type': product.get('product_type'),
                'status': product.get('status'),
                'tags': product.get('tags', '').split(', ') if product.get('tags') else [],
                'created_at': product.get('created_at'),
                'updated_at': product.get('updated_at'),
                'published_at': product.get('published_at'),
                'options': product.get('options', []),
                'images': [
                    {
                        'id': img['id'],
                        'position': img['position'],
                        'src': img['src'],
                        'alt': img.get('alt', '')
                    }
                    for img in product.get('images', [])
                ]
            }
            
            # Process variants
            for variant in product.get('variants', []):
                variant_data = {
                    **base_product,
                    'variant_id': variant['id'],
                    'variant_title': variant['title'],
                    'sku': variant.get('sku'),
                    'barcode': variant.get('barcode'),
                    'price': float(variant['price']) if variant.get('price') else None,
                    'compare_at_price': float(variant['compare_at_price']) if variant.get('compare_at_price') else None,
                    'inventory_quantity': variant.get('inventory_quantity'),
                    'inventory_policy': variant.get('inventory_policy'),
                    'fulfillment_service': variant.get('fulfillment_service'),
                    'weight': variant.get('weight'),
                    'weight_unit': variant.get('weight_unit'),
                    'option1': variant.get('option1'),
                    'option2': variant.get('option2'),
                    'option3': variant.get('option3'),
                    'taxable': variant.get('taxable'),
                    'requires_shipping': variant.get('requires_shipping'),
                    'variant_created_at': variant.get('created_at'),
                    'variant_updated_at': variant.get('updated_at')
                }
                transformed.append(variant_data)
        
        return transformed
    
    def save_to_json(self, products: List[Dict[str, Any]], filename: str = None):
        """Save products to JSON file"""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"shopify_products_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(products, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"Saved {len(products)} products to {filename}")
        return filename
    
    def save_to_csv(self, products: List[Dict[str, Any]], filename: str = None):
        """Save products to CSV file"""
        import csv
        
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"shopify_products_{timestamp}.csv"
        
        if not products:
            print("No products to save")
            return
        
        # Get all unique keys for CSV headers
        all_keys = set()
        for product in products:
            all_keys.update(product.keys())
        
        headers = sorted(list(all_keys))
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            
            for product in products:
                # Convert lists and complex objects to strings for CSV
                row = {}
                for key, value in product.items():
                    if isinstance(value, (list, dict)):
                        row[key] = json.dumps(value, ensure_ascii=False)
                    else:
                        row[key] = value
                writer.writerow(row)
        
        print(f"Saved {len(products)} product variants to {filename}")
        return filename


def main():
    """Main function to fetch and save Shopify products"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Fetch products from Shopify')
    parser.add_argument('--format', choices=['json', 'csv', 'both'], default='json',
                       help='Output format (default: json)')
    parser.add_argument('--output', help='Output filename (without extension)')
    parser.add_argument('--raw', action='store_true',
                       help='Save raw API response without transformation')
    
    args = parser.parse_args()
    
    try:
        # Initialize fetcher
        fetcher = ShopifyProductFetcher()
        
        # Fetch all products
        print("Fetching products from Shopify...")
        products = fetcher.fetch_products()
        
        if not products:
            print("No products found")
            return
        
        print(f"\nFetched {len(products)} products total")
        
        # Transform products unless raw flag is set
        if not args.raw:
            print("Transforming products...")
            products = fetcher.transform_products(products)
            print(f"Transformed into {len(products)} product variants")
        
        # Save to file(s)
        base_filename = args.output
        
        if args.format in ['json', 'both']:
            filename = f"{base_filename}.json" if base_filename else None
            fetcher.save_to_json(products, filename)
        
        if args.format in ['csv', 'both']:
            filename = f"{base_filename}.csv" if base_filename else None
            fetcher.save_to_csv(products, filename)
        
        # Print summary
        print("\nSummary:")
        print(f"- Total products/variants: {len(products)}")
        if not args.raw and products:
            unique_products = len(set(p['product_id'] for p in products))
            print(f"- Unique products: {unique_products}")
            print(f"- Average variants per product: {len(products) / unique_products:.1f}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()