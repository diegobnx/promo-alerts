#!/usr/bin/env python3
"""
Promo Alerts - Monitor RSS feeds for new travel promotions
"""

import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Optional

import feedparser
import requests
import yaml
from dateutil import parser as date_parser

# Importar APIs de aviação
try:
    from public_apis import AviationAPIIntegration
    AVIATION_APIS_AVAILABLE = True
except ImportError:
    AVIATION_APIS_AVAILABLE = False



# Importar APIs de preços focadas
try:
    from flight_price_apis import FlightPriceChecker
    FLIGHT_PRICE_APIS_AVAILABLE = True
except ImportError:
    FLIGHT_PRICE_APIS_AVAILABLE = False


class PromoAlertsMonitor:
    def __init__(self, feeds_file: str = "feeds.yml", seen_file: str = "../data/seen.json", filters_file: str = "filters.yml"):
        self.feeds_file = feeds_file
        self.filters_file = filters_file
        self.seen_file = Path(__file__).parent / seen_file
        self.seen_posts: Set[str] = set()
        self.new_posts: List[Dict] = []
        self.filtered_posts: List[Dict] = []
        self.rejected_posts: List[Dict] = []
        self.filters_config: Dict = {}
        
        # Initialize aviation APIs if available
        self.aviation_apis = AviationAPIIntegration() if AVIATION_APIS_AVAILABLE else None
        

        
        # Initialize price checker APIs if available
        self.price_checker = FlightPriceChecker() if FLIGHT_PRICE_APIS_AVAILABLE else None
        
        # Create data directory if it doesn't exist
        self.seen_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load configurations
        self.load_seen_posts()
        self.load_filters_config()
    
    def load_seen_posts(self):
        """Load previously seen post IDs from file"""
        if self.seen_file.exists():
            try:
                with open(self.seen_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.seen_posts = set(data.get('seen_posts', []))
                    print(f"✅ Loaded {len(self.seen_posts)} seen posts")
            except (json.JSONDecodeError, FileNotFoundError) as e:
                print(f"⚠️ Could not load seen posts: {e}")
                self.seen_posts = set()
        else:
            print("📝 No seen posts file found, starting fresh")
    
    def save_seen_posts(self):
        """Save seen post IDs to file"""
        try:
            data = {
                'seen_posts': list(self.seen_posts),
                'last_updated': datetime.now().isoformat()
            }
            with open(self.seen_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"💾 Saved {len(self.seen_posts)} seen posts")
        except Exception as e:
            print(f"❌ Error saving seen posts: {e}")
    
    def load_filters_config(self):
        """Load filters configuration from YAML file"""
        try:
            with open(self.filters_file, 'r', encoding='utf-8') as f:
                self.filters_config = yaml.safe_load(f)
                
            if self.filters_config.get('enabled', False):
                print(f"🔍 Filters loaded and enabled")
            else:
                print(f"📋 Filters loaded but disabled")
                
        except FileNotFoundError:
            print(f"⚠️ Filters file not found: {self.filters_file}")
            self.filters_config = {'enabled': False}
        except Exception as e:
            print(f"❌ Error loading filters: {e}")
            self.filters_config = {'enabled': False}
    
    def normalize_text(self, text: str) -> str:
        """Normalize text for matching"""
        if not text:
            return ""
        # Remove accents and convert to lowercase
        import unicodedata
        text = unicodedata.normalize('NFD', text)
        text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
        return text.lower().strip()
    
    def extract_price(self, text: str) -> Optional[float]:
        """Extract price from text"""
        if not text:
            return None
        
        # Look for R$ patterns
        price_patterns = [
            r'R\$\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)',  # R$ 1.234,56 or R$ 234,56
            r'(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)\s*reais',  # 1.234,56 reais
            r'por\s*R\$\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)',  # por R$ 234,56
            r'partir\s+de\s*R\$\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)',  # a partir de R$ 234,56
        ]
        
        for pattern in price_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                try:
                    # Convert Brazilian number format to float
                    price_str = matches[0].replace('.', '').replace(',', '.')
                    return float(price_str)
                except ValueError:
                    continue
        
        return None
    
    def check_route_filter(self, title: str, summary: str) -> bool:
        """Check if post matches route filters"""
        routes_config = self.filters_config.get('routes', {})
        if not routes_config.get('enabled', False):
            return True
        
        full_text = f"{title} {summary}".lower()
        normalized_text = self.normalize_text(full_text)
        
        # Check include routes
        include_routes = routes_config.get('include', [])
        if include_routes:
            for route in include_routes:
                if ' -> ' in route:
                    origin, destination = route.split(' -> ')
                    origin_norm = self.normalize_text(origin)
                    dest_norm = self.normalize_text(destination)
                    
                    # Check if both origin and destination are mentioned
                    if origin_norm in normalized_text and dest_norm in normalized_text:
                        return True
                else:
                    # Single city/location
                    if self.normalize_text(route) in normalized_text:
                        return True
            
            # If we have include routes but none matched
            return False
        
        # Check exclude routes
        exclude_routes = routes_config.get('exclude', [])
        for route in exclude_routes:
            if ' -> ' in route:
                origin, destination = route.split(' -> ')
                origin_norm = self.normalize_text(origin)
                dest_norm = self.normalize_text(destination)
                
                # If both are mentioned, exclude this post
                if origin_norm in normalized_text and dest_norm in normalized_text:
                    return False
            else:
                if self.normalize_text(route) in normalized_text:
                    return False
        
        return True
    
    def check_keyword_filter(self, title: str, summary: str) -> bool:
        """Check if post matches keyword filters - FOCO POSITIVO: Recife + Passagens + Milhas"""
        keywords_config = self.filters_config.get('keywords', {})
        if not keywords_config.get('enabled', False):
            return True
        
        full_text = f"{title} {summary}".lower()
        normalized_text = self.normalize_text(full_text)
        
        # REGRA EXPANDIDA: Deve mencionar Recife/PE/REC E algo relacionado a passagens/viagem/milhas
        
        # 1. Deve mencionar Recife/PE/REC/Pernambuco (ULTRA-ESPECÍFICO)
        has_recife = (
            self.normalize_text('recife') in normalized_text or
            self.normalize_text('pernambuco') in normalized_text or
            # REC como código de aeroporto (muito específico)
            ' rec ' in f" {normalized_text} " or
            '-rec ' in normalized_text or
            ' rec-' in normalized_text or
            'rec.' in normalized_text or
            'gru-rec' in normalized_text or
            'sp-rec' in normalized_text or
            # PE APENAS em contextos muito específicos de estado
            ' pe ' in f" {normalized_text} " or
            'sp-pe' in normalized_text or
            'para pe ' in f" {normalized_text} " or  # Para PE (estado)
            'destino pe' in normalized_text or
            'rumo pe' in normalized_text
        )
        
        # 2. Deve mencionar termos ESPECÍFICOS de passagens/voos (removendo termos genéricos)
        has_passagem_terms = any(term in normalized_text for term in [
            self.normalize_text('passagem'),
            self.normalize_text('passagens'),
            self.normalize_text('voo'),
            self.normalize_text('voos'),
            self.normalize_text('viagem'),
            self.normalize_text('viagens'),
            # Companhias aéreas (indicam contexto de voo)
            self.normalize_text('azul'),
            self.normalize_text('gol'),
            self.normalize_text('latam'),
            # Aeroportos (indicam contexto de voo)
            self.normalize_text('guarulhos'),
            self.normalize_text('congonhas'),
            'gru',
            'cgh',
            # Contextos específicos de voo
            self.normalize_text('voar'),
            self.normalize_text('aereo'),
            self.normalize_text('aerea'),
            self.normalize_text('aereas'),
            self.normalize_text('bilhete'),
            self.normalize_text('bilhetes')
        ])
        
        # 3. NOVO: Termos relacionados a MILHAS (da configuração)
        miles_keywords = keywords_config.get('miles_keywords', [])
        has_miles_terms = any(self.normalize_text(term) in normalized_text for term in miles_keywords)
        
        # Deve ter Recife E (passagens OU milhas) para passar
        return has_recife and (has_passagem_terms or has_miles_terms)
    
    def check_price_filter(self, title: str, summary: str) -> bool:
        """Check if post matches price filters"""
        price_config = self.filters_config.get('price', {})
        if not price_config.get('enabled', False):
            return True
        
        full_text = f"{title} {summary}"
        price = self.extract_price(full_text)
        
        if price is None:
            return True  # If no price found, don't filter out
        
        # Check if it's likely international (rough heuristic)
        is_international = any(word in full_text.lower() for word in [
            'internacional', 'europa', 'eua', 'asia', 'africa', 'oceania',
            'paris', 'london', 'new york', 'tokyo', 'madrid', 'rome'
        ])
        
        max_price = price_config.get('international_max', 2500) if is_international else price_config.get('domestic_max', 800)
        
        return price <= max_price
    
    def check_airline_filter(self, title: str, summary: str) -> bool:
        """Check if post matches airline filters"""
        airlines_config = self.filters_config.get('airlines', {})
        if not airlines_config.get('enabled', False):
            return True
        
        full_text = f"{title} {summary}".lower()
        
        # Check include airlines
        include_airlines = airlines_config.get('include', [])
        if include_airlines:
            for airline in include_airlines:
                if airline.lower() in full_text:
                    break
            else:
                return False
        
        # Check exclude airlines
        exclude_airlines = airlines_config.get('exclude', [])
        for airline in exclude_airlines:
            if airline.lower() in full_text:
                return False
        
        return True
    
    def apply_filters(self, post: Dict) -> bool:
        """Apply all filters to a post - FOCO ABSOLUTO EM RECIFE + PASSAGENS"""
        if not self.filters_config.get('enabled', False):
            return True
        
        title = post.get('title', '')
        summary = post.get('summary', '')
        
        # REGRA ÚNICA E ABSOLUTA: Deve mencionar Recife/PE/REC + passagem/voo
        # Ignora todos os outros filtros e aplica apenas a lógica de keywords
        
        keyword_passed = self.check_keyword_filter(title, summary)
        
        # Log se rejeitado (apenas primeiros 3 por feed para não spammar)
        if not keyword_passed and self.filters_config.get('advanced', {}).get('log_rejected_posts', False):
            if not hasattr(self, '_rejected_count_per_feed'):
                self._rejected_count_per_feed = {}
            
            feed_name = post.get('feed_name', 'unknown')
            count = self._rejected_count_per_feed.get(feed_name, 0)
            
            if count < 3:  # Mostra apenas os primeiros 3 rejeitados por feed
                print(f"  🔍 Post filtered out: NÃO é sobre passagens/milhas para Recife")
                print(f"    📝 Title: {title[:60]}...")
                self._rejected_count_per_feed[feed_name] = count + 1
            elif count == 3:  # No quarto, mostra mensagem resumida
                print(f"  🔍 ... (mais posts rejeitados - não são sobre Recife)")
                self._rejected_count_per_feed[feed_name] = count + 1
        
        return keyword_passed
    
    def load_feeds(self) -> List[Dict]:
        """Load feed configuration from YAML file"""
        try:
            with open(self.feeds_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                feeds = config.get('feeds', [])
                print(f"📋 Loaded {len(feeds)} feeds from configuration")
                return feeds
        except Exception as e:
            print(f"❌ Error loading feeds configuration: {e}")
            return []
    
    def fetch_feed(self, feed_url: str, feed_name: str, progress: str = "") -> List[Dict]:
        """Fetch and parse RSS feed"""
        posts = []
        
        try:
            print(f"🔍 {progress}Fetching feed: {feed_name}")
            
            # Set a proper User-Agent to avoid blocking
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/rss+xml, application/xml, text/xml, */*',
                'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
                'Cache-Control': 'no-cache'
            }
            
            # Fetch with timeout and retry logic (otimizado)
            max_retries = 2
            for attempt in range(max_retries):
                try:
                    response = requests.get(feed_url, headers=headers, timeout=15, allow_redirects=True)
                    response.raise_for_status()
                    break
                except requests.exceptions.Timeout:
                    if attempt < max_retries - 1:
                        print(f"  ⏱️ Timeout on attempt {attempt + 1}, retrying...")
                        time.sleep(1)
                        continue
                    else:
                        print(f"  ❌ Feed timeout after {max_retries} attempts, skipping...")
                        return []
                except requests.exceptions.RequestException as e:
                    if attempt < max_retries - 1 and "403" not in str(e):
                        print(f"  🔄 Error on attempt {attempt + 1}, retrying...")
                        time.sleep(1)
                        continue
                    else:
                        raise
            
            # Parse feed
            feed = feedparser.parse(response.content)
            
            if feed.bozo:
                print(f"⚠️ Feed parsing warning for {feed_name}: {feed.bozo_exception}")
            
            # Process entries (check if entries exist)
            if not feed.entries:
                print(f"  ⚠️ No entries found in feed")
            else:
                # Process entries (limitado a 5 para ser mais rápido)
                for entry in feed.entries[:5]:  # Limit to latest 5 posts
                    # Create unique ID for the post
                    post_id = f"{feed_name}:{entry.get('id', entry.get('link', entry.get('title', '')))}".strip()
                    
                    if not post_id or post_id.endswith(':'):
                        continue
                    
                    # Skip if already seen
                    if post_id in self.seen_posts:
                        continue
                    
                    # Parse publication date
                    pub_date = None
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        pub_date = datetime(*entry.published_parsed[:6])
                    elif hasattr(entry, 'published'):
                        try:
                            pub_date = date_parser.parse(entry.published)
                        except:
                            pass
                    
                    # Extract post data
                    post = {
                        'id': post_id,
                        'feed_name': feed_name,
                        'title': entry.get('title', 'No title').strip(),
                        'link': entry.get('link', ''),
                        'summary': entry.get('summary', entry.get('description', '')),
                        'published': pub_date.isoformat() if pub_date else None,
                        'discovered_at': datetime.now().isoformat()
                    }
                    
                    # Apply filters before adding to results
                    if self.apply_filters(post):
                        # Enrich with aviation APIs data if available
                        if self.aviation_apis:
                            post = self.aviation_apis.enhance_post_with_apis(post)
                        

                        
                        # Enrich with current price data for better deal analysis
                        if self.price_checker:
                            post = self.enhance_post_with_price_analysis(post)
                        
                        posts.append(post)
                        self.filtered_posts.append(post)
                    else:
                        self.rejected_posts.append(post)
                    
                    # Always add to seen posts to avoid reprocessing
                    self.seen_posts.add(post_id)
            
            print(f"  ✅ Found {len(posts)} new posts from {feed_name}")
            
        except requests.RequestException as e:
            print(f"  ❌ Network error for {feed_name}: {e}")
        except Exception as e:
            print(f"  ❌ Error processing {feed_name}: {e}")
        
        return posts
    
    def monitor_feeds(self):
        """Monitor all configured feeds for new posts"""
        feeds = self.load_feeds()
        
        if not feeds:
            print("❌ No feeds configured")
            return
        
        print(f"🚀 Starting monitoring of {len(feeds)} feeds...")
        print("=" * 50)
        
        for i, feed in enumerate(feeds, 1):
            feed_name = feed.get('name', 'Unknown Feed')
            feed_url = feed.get('url', '')
            
            if not feed_url:
                print(f"⚠️ No URL configured for feed: {feed_name}")
                continue
            
            progress = f"[{i}/{len(feeds)}] "
            new_posts = self.fetch_feed(feed_url, feed_name, progress)
            self.new_posts.extend(new_posts)
            
            # Small delay between feeds to be respectful (reduzido)
            time.sleep(0.5)
        
        print("=" * 50)
        
        # Show filtering statistics
        if self.filters_config.get('enabled', False):
            total_found = len(self.filtered_posts) + len(self.rejected_posts)
            print(f"📊 Filtering Summary:")
            print(f"  🔍 Total posts found: {total_found}")
            print(f"  ✅ Posts passed filters: {len(self.filtered_posts)}")
            print(f"  ❌ Posts rejected by filters: {len(self.rejected_posts)}")
            
            if len(self.rejected_posts) > 0 and self.filters_config.get('advanced', {}).get('log_rejected_posts', False):
                print(f"\n🚫 Rejected posts examples:")
                for post in self.rejected_posts[:3]:  # Show first 3 rejected
                    print(f"  📝 {post['title'][:50]}...")
        else:
            print(f"📊 Summary: Found {len(self.new_posts)} new posts total (no filters applied)")
        
        # Check minimum posts threshold
        min_posts = self.filters_config.get('advanced', {}).get('min_posts_to_notify', 1)
        if self.filters_config.get('enabled', False) and len(self.filtered_posts) < min_posts:
            print(f"⚠️ Only {len(self.filtered_posts)} posts passed filters (minimum: {min_posts})")
            print(f"📵 Skipping notifications due to low post count")
            
            # Send "no promotions found" notification if enabled and enough posts analyzed
            if self.filters_config.get('advanced', {}).get('notify_when_no_results', False):
                # Calculate total posts analyzed from new_posts + rejected_posts
                total_analyzed = len(self.new_posts) + len(self.rejected_posts)
                min_analyzed = self.filters_config.get('advanced', {}).get('no_results_min_posts_analyzed', 10)
                
                if total_analyzed >= min_analyzed:
                    self.send_no_promotions_notification(total_analyzed, len(self.rejected_posts))
                else:
                    print(f"📊 Only {total_analyzed} posts analyzed (minimum {min_analyzed} for no-results notification)")
            
            self.new_posts = []  # Clear posts to skip notifications
        else:
            self.new_posts = self.filtered_posts if self.filters_config.get('enabled', False) else self.new_posts
        
        # Save seen posts
        self.save_seen_posts()
        
        # Display new posts
        self.display_new_posts()
    
    def display_new_posts(self):
        """Display summary of new posts found"""
        if not self.new_posts:
            print("✨ No new posts found")
            return
        
        print(f"\n🔥 {len(self.new_posts)} NEW POSTS FOUND!")
        print("=" * 50)
        
        for post in self.new_posts:
            print(f"\n📰 {post['feed_name']}")
            print(f"   📝 {post['title']}")
            print(f"   🔗 {post['link']}")
            if post['published']:
                print(f"   📅 {post['published']}")
            
            # Show summary if available and not too long
            summary = post.get('summary', '')
            if summary and len(summary) < 300:
                # Clean HTML tags from summary
                import re
                clean_summary = re.sub('<[^<]+?>', '', summary).strip()
                if clean_summary:
                    print(f"   💬 {clean_summary[:200]}{'...' if len(clean_summary) > 200 else ''}")
        
        print("\n" + "=" * 50)
    
    def send_telegram_notification(self):
        """Send notification to Telegram"""
        if not self.new_posts:
            return
        
        bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        chat_id = os.environ.get('TELEGRAM_CHAT_ID')
        
        if not bot_token or not chat_id:
            print("⚠️ Telegram credentials not configured, skipping notification")
            return
        
        try:
            # Create message with top posts
            message = "🔥 *NOVAS PROMOÇÕES ENCONTRADAS!*\n\n"
            
            # Group posts by feed and show top 2 per feed
            feed_posts = {}
            for post in self.new_posts:
                feed_name = post['feed_name']
                if feed_name not in feed_posts:
                    feed_posts[feed_name] = []
                feed_posts[feed_name].append(post)
            
            # Show up to 2 posts per feed, max 8 total
            total_shown = 0
            for feed_name, posts in feed_posts.items():
                if total_shown >= 8:
                    break
                    
                message += f"📰 *{feed_name}*\n"
                
                for post in posts[:2]:  # Max 2 per feed
                    if total_shown >= 8:
                        break
                    
                    title = post['title'][:80] + "..." if len(post['title']) > 80 else post['title']
                    message += f"📝 [{title}]({post['link']})\n"
                    total_shown += 1
                
                message += "\n"
            
            # Add summary
            remaining = len(self.new_posts) - total_shown
            if remaining > 0:
                message += f"... e mais {remaining} promoções!\n\n"
            
            message += f"📊 *Total:* {len(self.new_posts)} novas promoções\n"
            message += f"⏰ *Detectado em:* {datetime.now().strftime('%H:%M - %d/%m/%Y')}"
            
            # Send to Telegram
            telegram_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                'chat_id': chat_id,
                'text': message,
                'parse_mode': 'Markdown',
                'disable_web_page_preview': True
            }
            
            response = requests.post(telegram_url, json=payload, timeout=10)
            
            if response.status_code == 200:
                print(f"✅ Telegram notification sent successfully!")
            else:
                print(f"❌ Failed to send Telegram notification: {response.status_code}")
                print(f"Response: {response.text}")
                
        except Exception as e:
            print(f"❌ Error sending Telegram notification: {e}")
    
    def send_no_promotions_notification(self, total_analyzed: int, rejected_count: int):
        """Send notification when no Recife promotions are found"""
        bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        chat_id = os.environ.get('TELEGRAM_CHAT_ID')
        
        if not bot_token or not chat_id:
            print("⚠️ Telegram credentials not configured, skipping 'no promotions' notification")
            return
        
        try:
            current_time = datetime.now().strftime('%H:%M - %d/%m/%Y')
            
            message = f"""🔍 **MONITORAMENTO ATIVO**

📊 **Análise concluída:**
• {total_analyzed} posts analisados
• {rejected_count} posts rejeitados
• 0 promoções de passagens para Recife encontradas

🎯 **Filtro funcionando perfeitamente!**
Sistema buscando apenas passagens específicas para Recife/PE.

⏰ Verificado em: {current_time}
🔄 Próxima verificação em 2-3 horas"""

            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            data = {
                'chat_id': chat_id,
                'text': message,
                'parse_mode': 'Markdown'
            }
            
            response = requests.post(url, data=data, timeout=30)
            
            if response.status_code == 200:
                print(f"✅ 'No promotions' notification sent to Telegram")
            else:
                print(f"❌ Failed to send 'no promotions' notification: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Error sending 'no promotions' notification: {e}")
    
    def enhance_post_with_price_analysis(self, post: Dict) -> Dict:
        """
        Enriquecer post com análise de preços atuais SP → Recife
        Só busca preços se o post for realmente sobre Recife
        """
        if not self._is_post_about_recife_flights(post):
            return post
        
        try:
            print(f"💰 Analisando preços para: {post.get('title', '')[:50]}...")
            
            # Buscar preços atuais (cache simples para evitar spam da API)
            cache_key = f"sp_recife_prices_{datetime.now().strftime('%Y%m%d_%H')}"
            
            if not hasattr(self, '_price_cache'):
                self._price_cache = {}
            
            if cache_key not in self._price_cache:
                price_analysis = self.price_checker.get_complete_sp_recife_analysis()
                self._price_cache[cache_key] = price_analysis
            else:
                price_analysis = self._price_cache[cache_key]
            
            if 'error' not in price_analysis:
                # Extrair preço de promoção do post (se mencionado)
                promo_price = self.extract_price(f"{post.get('title', '')} {post.get('summary', '')}")
                
                current_market_price = price_analysis['summary']['cheapest_price_brl']
                price_rating = price_analysis['summary']['price_rating']
                
                # Análise da oferta
                deal_analysis = {
                    'current_market_price_brl': current_market_price,
                    'market_price_rating': price_rating,
                    'has_promotion_price': promo_price is not None
                }
                
                if promo_price:
                    savings = current_market_price - promo_price
                    deal_analysis.update({
                        'promotion_price_brl': promo_price,
                        'savings_vs_market': savings,
                        'discount_percentage': round((savings / current_market_price) * 100, 1) if current_market_price > 0 else 0,
                        'is_good_deal': savings > 50 and promo_price < 500,  # Economiza >R$50 e <R$500
                        'deal_quality': self._rate_deal_quality(promo_price, current_market_price)
                    })
                else:
                    deal_analysis.update({
                        'promotion_price_brl': None,
                        'note': 'Preço da promoção não identificado no texto'
                    })
                
                # Adicionar dados de milhas
                if promo_price:
                    miles_estimates = self.price_checker.estimate_miles_prices(promo_price)
                    deal_analysis['miles_alternative'] = {
                        'best_program': miles_estimates['best_miles_option'],
                        'estimated_miles': miles_estimates['programs'][miles_estimates['best_miles_option']]['estimated_miles'],
                        'worth_using_miles': miles_estimates['programs'][miles_estimates['best_miles_option']]['worth_using_miles']
                    }
                
                post['price_analysis'] = deal_analysis
                
        except Exception as e:
            print(f"⚠️ Erro na análise de preços: {e}")
            post['price_analysis'] = {'error': str(e)}
        
        return post
    
    def _is_post_about_recife_flights(self, post: Dict) -> bool:
        """Verificar se post é especificamente sobre voos para Recife"""
        text = f"{post.get('title', '')} {post.get('summary', '')}".lower()
        
        # Deve mencionar Recife/PE/REC
        has_recife = any(term in text for term in [
            'recife', 'pernambuco', ' pe ', ' rec ', '-rec', 'gru-rec', 'sp-rec'
        ])
        
        # E deve mencionar voos/passagens
        has_flight_terms = any(term in text for term in [
            'voo', 'voos', 'passagem', 'passagens', 'voar', 'aereo', 'aerea'
        ])
        
        return has_recife and has_flight_terms
    
    def _rate_deal_quality(self, promo_price: float, market_price: float) -> str:
        """Avaliar qualidade da oferta"""
        if promo_price >= market_price:
            return 'RUIM'
        
        savings_pct = ((market_price - promo_price) / market_price) * 100
        
        if savings_pct >= 30:
            return 'EXCELENTE'
        elif savings_pct >= 15:
            return 'MUITO_BOA'
        elif savings_pct >= 5:
            return 'BOA'
        else:
            return 'REGULAR'
    

    
    def create_github_output(self):
        """Create GitHub Actions output for notifications"""
        if not self.new_posts:
            return
        
        # Set GitHub Actions output
        github_output = os.environ.get('GITHUB_OUTPUT')
        if github_output:
            with open(github_output, 'a', encoding='utf-8') as f:
                f.write(f"new_posts_count={len(self.new_posts)}\n")
                
                # Create a summary for the first few posts
                summary_posts = self.new_posts[:3]  # Show first 3 posts
                summary_text = "🔥 NOVAS PROMOÇÕES ENCONTRADAS!\n\n"
                
                for post in summary_posts:
                    summary_text += f"📰 **{post['feed_name']}**\n"
                    summary_text += f"📝 [{post['title']}]({post['link']})\n\n"
                
                if len(self.new_posts) > 3:
                    summary_text += f"... e mais {len(self.new_posts) - 3} promoções!\n"
                
                # Escape for GitHub Actions
                summary_text = summary_text.replace('\n', '\\n').replace('"', '\\"')
                f.write(f"posts_summary={summary_text}\n")


def main():
    """Main execution function"""
    print("🎯 Promo Alerts Monitor")
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        monitor = PromoAlertsMonitor()
        monitor.monitor_feeds()
        monitor.send_telegram_notification()
        monitor.create_github_output()
        
        print(f"\n✅ Monitoring completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
    except KeyboardInterrupt:
        print("\n⏹️ Monitoring stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
