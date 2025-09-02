#!/usr/bin/env python3
"""
Fetch products from Shopify API and save to JSON file
"""

import json
import os
import sys
import time
from typing import Dict, List, Any, Optional
import requests
from dotenv import load_dotenv

load_dotenv()


class ShopifyFetcher:
    def __init__(self):
        """Initialize Shopify API client"""
        self.access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
        self.api_version = os.getenv('SHOPIFY_API_VERSION', '2024-01')
        
        if not self.access_token:
            raise ValueError("SHOPIFY_ACCESS_TOKEN must be set in environment variables")
    
    def fetch_products(self, shop_url: str, limit: int = 250) -> List[Dict[str, Any]]:
        """
        Fetch all products from Shopify API with pagination
        
        Args:
            shop_url: Shopify shop URL
            limit: Number of products per page (max 250)
            
        Returns:
            List of all products with their variants
        """
        # Build base URL for API calls
        base_url = f"{shop_url.rstrip('/')}/admin/api/{self.api_version}"
        endpoint = f"{base_url}/products.json"
        
        # Set up headers
        headers = {
            'X-Shopify-Access-Token': self.access_token,
            'Content-Type': 'application/json'
        }
        
        all_products = []
        params = {
            'limit': min(limit, 250),  # Shopify max is 250
            'fields': 'id,title,handle,body_html,vendor,product_type,created_at,updated_at,published_at,tags,status,variants,images,options'
        }
        
        page_info = None
        page_count = 0
        
        print(f"Fetching products from {shop_url}...")
        
        while True:
            # Use page_info for pagination after first request
            if page_info:
                params = {'page_info': page_info, 'limit': params['limit']}
            
            try:
                response = requests.get(endpoint, headers=headers, params=params)
                response.raise_for_status()
                
                data = response.json()
                products = data.get('products', [])
                
                if not products:
                    break
                
                all_products.extend(products)
                page_count += 1
                
                print(f"  Fetched page {page_count}: {len(products)} products (Total: {len(all_products)})")
                
                # Check for next page
                link_header = response.headers.get('Link', '')
                page_info = self._extract_page_info(link_header, 'next')
                
                if not page_info:
                    break
                
                # Rate limiting - Shopify allows 2 requests per second
                time.sleep(0.5)
                
            except requests.exceptions.RequestException as e:
                print(f"Error fetching products: {e}")
                if hasattr(e, 'response') and e.response is not None:
                    print(f"Response Status: {e.response.status_code}")
                    print(f"Response Body: {e.response.text}")
                raise
        
        print(f"Successfully fetched {len(all_products)} products from Shopify API")
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
    
    def save_to_json(self, products: List[Dict[str, Any]], filename: str):
        """Save products to JSON file"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(products, f, indent=2, ensure_ascii=False, default=str)
        
        total_variants = sum(len(p.get('variants', [])) for p in products)
        total_images = sum(len(p.get('images', [])) for p in products)
        
        print(f"\nSaved to {filename}:")
        print(f"  - Products: {len(products)}")
        print(f"  - Variants: {total_variants}")
        print(f"  - Images: {total_images}")


def main():
    """Main function to fetch products"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Fetch Shopify products to JSON file')
    parser.add_argument('shopify_url', help='Shopify store URL (e.g., https://store.myshopify.com)')
    parser.add_argument('output_file', help='Output JSON file path')
    parser.add_argument('--limit', type=int, default=250, help='Products per page (max 250)')
    
    args = parser.parse_args()
    
    try:
        fetcher = ShopifyFetcher()
        products = fetcher.fetch_products(args.shopify_url, args.limit)
        fetcher.save_to_json(products, args.output_file)
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()