"""
Niche Researcher - Scraper Engine
Browser automation module for collecting data from various platforms
"""

import time
import random
import logging
import yaml
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from browser_use import Browser

# Setup logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('scraper_engine')

# Load configuration
try:
    with open('config.yaml', 'r') as config_file:
        config = yaml.safe_load(config_file)
except Exception as e:
    logger.error(f"Error loading configuration: {e}")
    config = {}

# Platform-specific CSS selectors
PLATFORM_SELECTORS = {
    'tiktok': {
        'hashtags': '.hashtag',
        'views': '.video-count',
        'fallback_hashtags': 'a[href*="/tag/"]'
    },
    'amazon': {
        'products': '[data-zg-item]',
        'product_name': '.p13n-sc-truncated',
        'price': '.p13n-sc-price',
        'rating': '.a-icon-alt',
        'fallback_products': '.zg-item'
    },
    'reddit': {
        'posts': '[data-testid="post-container"]',
        'title': '[data-testid="post-title"]',
        'upvotes': '[data-testid="upvote-count"]',
        'comments': '[data-testid="comment-count"]',
        'fallback_posts': '.Post'
    },
    'youtube': {
        'videos': 'ytd-video-renderer,ytd-grid-video-renderer',
        'title': '#video-title',
        'views': '#metadata-line span:first-child',
        'date': '#metadata-line span:last-child',
        'fallback_videos': '.yt-simple-endpoint.ytd-video-renderer'
    },
}

class ProxyManager:
    """Manages proxy rotation for web scraping"""
    
    def __init__(self, proxy_config):
        self.enabled = proxy_config.get('enabled', False)
        self.rotation = proxy_config.get('rotation', False)
        self.proxies = proxy_config.get('providers', [])
        self.current_index = 0
        
    def get_proxy(self):
        """Returns the next proxy in the rotation"""
        if not self.enabled or not self.proxies:
            return None
            
        if self.rotation:
            proxy = self.proxies[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.proxies)
        else:
            proxy = self.proxies[0]
            
        return proxy.get('url')
        
class UserAgentManager:
    """Manages user agent rotation for web scraping"""
    
    def __init__(self, user_agents):
        self.user_agents = user_agents or [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        ]
        
    def get_random_user_agent(self):
        """Returns a random user agent from the list"""
        return random.choice(self.user_agents)

class ScraperEngine:
    """Main scraper engine for collecting data from various platforms"""
    
    def __init__(self):
        scraping_config = config.get('scraping', {})
        self.max_retries = scraping_config.get('max_retries', 3)
        self.timeout = scraping_config.get('timeout', 30)
        self.delay = scraping_config.get('delay_between_requests', 2)
        
        self.proxy_manager = ProxyManager(config.get('proxy', {}))
        self.user_agent_manager = UserAgentManager(scraping_config.get('user_agents', []))
        
        self.platforms_config = config.get('platforms', [])
        
    def _check_for_captcha(self, html_content):
        """Check if the response contains a CAPTCHA challenge"""
        captcha_indicators = [
            'captcha', 'robot', 'human verification', 
            'security check', 'prove you\'re human'
        ]
        
        html_lower = html_content.lower()
        for indicator in captcha_indicators:
            if indicator in html_lower:
                return True
        return False
    
    def _handle_captcha(self, driver):
        """Handle CAPTCHA detection"""
        logger.warning("CAPTCHA detected! Manual intervention required.")
        print("\n⚠️ CAPTCHA detected! Please solve the CAPTCHA in the browser window.")
        print("Once solved, press Enter to continue...")
        input()  # Wait for user to solve CAPTCHA and press Enter
        # Return the updated page content after CAPTCHA is solved
        return driver.page_source
        
    def _make_request_with_retry(self, url, use_browser=True):
        """Make a request with retry logic"""
        for attempt in range(self.max_retries):
            try:
                if use_browser:
                    proxy = self.proxy_manager.get_proxy()
                    user_agent = self.user_agent_manager.get_random_user_agent()
                    
                    with Browser(headless=True, proxy=proxy, user_agent=user_agent) as driver:
                        driver.goto(url)
                        driver.wait(2)  # Wait for dynamic content to load
                        
                        # Check for CAPTCHA
                        if self._check_for_captcha(driver.page_source):
                            content = self._handle_captcha(driver)
                        else:
                            content = driver.page_source
                            
                        return content
                else:
                    # Use requests for simpler pages
                    headers = {'User-Agent': self.user_agent_manager.get_random_user_agent()}
                    proxy = self.proxy_manager.get_proxy()
                    proxies = {'http': proxy, 'https': proxy} if proxy else None
                    
                    response = requests.get(url, headers=headers, proxies=proxies, timeout=self.timeout)
                    response.raise_for_status()
                    
                    # Check for CAPTCHA in response content
                    if self._check_for_captcha(response.text):
                        logger.warning("CAPTCHA detected in non-browser request. Switching to browser mode.")
                        return self._make_request_with_retry(url, use_browser=True)
                        
                    return response.text
                    
            except Exception as e:
                logger.warning(f"Attempt {attempt+1}/{self.max_retries} failed: {e}")
                if attempt < self.max_retries - 1:
                    wait_time = self.delay * (attempt + 1)  # Exponential backoff
                    logger.info(f"Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Failed to retrieve {url} after {self.max_retries} attempts")
                    return None
    
    def scrape_tiktok_hashtags(self, tag="affiliatemarketing"):
        """Scrape TikTok hashtag data"""
        platform_config = next((p for p in self.platforms_config if p.get('name') == 'tiktok'), {})
        base_url = platform_config.get('base_url', "https://www.tiktok.com/tag/")
        
        url = f"{base_url}{tag}"
        logger.info(f"Scraping TikTok hashtag: {tag}")
        
        html_content = self._make_request_with_retry(url)
        if not html_content:
            return []
            
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Try primary selector, fall back to alternative if needed
        hashtags = soup.select(PLATFORM_SELECTORS['tiktok']['hashtags'])
        if not hashtags:
            logger.info("Primary selector failed, trying fallback selector")
            hashtags = soup.select(PLATFORM_SELECTORS['tiktok']['fallback_hashtags'])
            
        data = []
        for tag in hashtags:
            try:
                tag_name = tag.text.strip()
                # Some basic cleaning to remove # symbol if present
                tag_name = tag_name.lstrip('#')
                
                # Find view count element near the hashtag if possible
                view_element = tag.find_next(PLATFORM_SELECTORS['tiktok']['views'])
                views = view_element.text.strip() if view_element else "N/A"
                
                data.append({
                    'platform': 'tiktok',
                    'type': 'hashtag',
                    'name': tag_name,
                    'views': views,
                    'url': f"{base_url}{tag_name}"
                })
            except Exception as e:
                logger.warning(f"Error parsing TikTok hashtag: {e}")
                
        return data
        
    def scrape_amazon_bestsellers(self, category="electronics"):
        """Scrape Amazon bestseller data"""
        platform_config = next((p for p in self.platforms_config if p.get('name') == 'amazon'), {})
        base_url = platform_config.get('base_url', "https://www.amazon.com/best-sellers/")
        
        url = f"{base_url}{category}"
        logger.info(f"Scraping Amazon bestsellers for category: {category}")
        
        html_content = self._make_request_with_retry(url)
        if not html_content:
            return []
            
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Try primary selector, fall back to alternative if needed
        products = soup.select(PLATFORM_SELECTORS['amazon']['products'])
        if not products:
            logger.info("Primary selector failed, trying fallback selector")
            products = soup.select(PLATFORM_SELECTORS['amazon']['fallback_products'])
            
        data = []
        for product in products:
            try:
                # Get product details
                name_element = product.select_one(PLATFORM_SELECTORS['amazon']['product_name'])
                price_element = product.select_one(PLATFORM_SELECTORS['amazon']['price'])
                rating_element = product.select_one(PLATFORM_SELECTORS['amazon']['rating'])
                
                name = name_element.text.strip() if name_element else "N/A"
                price = price_element.text.strip() if price_element else "N/A"
                rating = rating_element.text.strip() if rating_element else "N/A"
                
                data.append({
                    'platform': 'amazon',
                    'type': 'product',
                    'category': category,
                    'name': name,
                    'price': price,
                    'rating': rating
                })
            except Exception as e:
                logger.warning(f"Error parsing Amazon product: {e}")
                
        return data
        
    def scrape_reddit_posts(self, subreddit="affiliatemarketing"):
        """Scrape Reddit posts data"""
        platform_config = next((p for p in self.platforms_config if p.get('name') == 'reddit'), {})
        base_url = platform_config.get('base_url', "https://www.reddit.com/r/")
        
        url = f"{base_url}{subreddit}"
        logger.info(f"Scraping Reddit posts for subreddit: {subreddit}")
        
        html_content = self._make_request_with_retry(url)
        if not html_content:
            return []
            
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Try primary selector, fall back to alternative if needed
        posts = soup.select(PLATFORM_SELECTORS['reddit']['posts'])
        if not posts:
            logger.info("Primary selector failed, trying fallback selector")
            posts = soup.select(PLATFORM_SELECTORS['reddit']['fallback_posts'])
            
        data = []
        for post in posts:
            try:
                # Get post details
                title_element = post.select_one(PLATFORM_SELECTORS['reddit']['title'])
                upvotes_element = post.select_one(PLATFORM_SELECTORS['reddit']['upvotes'])
                comments_element = post.select_one(PLATFORM_SELECTORS['reddit']['comments'])
                
                title = title_element.text.strip() if title_element else "N/A"
                upvotes = upvotes_element.text.strip() if upvotes_element else "0"
                comments = comments_element.text.strip() if comments_element else "0"
                
                data.append({
                    'platform': 'reddit',
                    'type': 'post',
                    'subreddit': subreddit,
                    'title': title,
                    'upvotes': upvotes,
                    'comments': comments
                })
            except Exception as e:
                logger.warning(f"Error parsing Reddit post: {e}")
                
        return data

    def scrape_youtube_videos(self, query="affiliate marketing"):
        """Scrape YouTube videos data"""
        query_formatted = query.replace(' ', '+')
        url = f"https://www.youtube.com/results?search_query={query_formatted}"
        logger.info(f"Scraping YouTube videos for query: {query}")
        
        html_content = self._make_request_with_retry(url)
        if not html_content:
            return []
            
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Try primary selector, fall back to alternative if needed
        videos = soup.select(PLATFORM_SELECTORS['youtube']['videos'])
        if not videos:
            logger.info("Primary selector failed, trying fallback selector")
            videos = soup.select(PLATFORM_SELECTORS['youtube']['fallback_videos'])
            
        data = []
        for video in videos[:10]:  # Limit to first 10 videos
            try:
                # Get video details
                title_element = video.select_one(PLATFORM_SELECTORS['youtube']['title'])
                views_element = video.select_one(PLATFORM_SELECTORS['youtube']['views'])
                date_element = video.select_one(PLATFORM_SELECTORS['youtube']['date'])
                
                title = title_element.text.strip() if title_element else "N/A"
                views = views_element.text.strip() if views_element else "N/A"
                date = date_element.text.strip() if date_element else "N/A"
                
                # Extract video ID from href if available
                video_id = None
                if title_element and title_element.has_attr('href'):
                    video_id = title_element['href'].split('=')[-1]
                
                data.append({
                    'platform': 'youtube',
                    'type': 'video',
                    'query': query,
                    'title': title,
                    'views': views,
                    'date': date,
                    'video_id': video_id,
                    'url': f"https://www.youtube.com/watch?v={video_id}" if video_id else "N/A"
                })
            except Exception as e:
                logger.warning(f"Error parsing YouTube video: {e}")
                
        return data

    def scrape_all_platforms(self, max_workers=5):
        """Scrape data from all enabled platforms"""
        all_data = []
        enabled_platforms = [p for p in self.platforms_config if p.get('enabled', True)]
        
        # Create scraping tasks based on enabled platforms
        scraping_tasks = []
        
        for platform in enabled_platforms:
            platform_name = platform.get('name')
            
            if platform_name == 'tiktok':
                tags = platform.get('tags', ["affiliatemarketing"])
                for tag in tags:
                    scraping_tasks.append(('tiktok', tag))
                    
            elif platform_name == 'amazon':
                categories = platform.get('categories', ["electronics"])
                for category in categories:
                    scraping_tasks.append(('amazon', category))
                    
            elif platform_name == 'reddit':
                subreddits = platform.get('subreddits', ["affiliatemarketing"])
                for subreddit in subreddits:
                    scraping_tasks.append(('reddit', subreddit))
                    
            elif platform_name == 'youtube':
                queries = platform.get('search_queries', ["affiliate marketing"])
                for query in queries:
                    scraping_tasks.append(('youtube', query))
        
        # Rate limiting - only process a few tasks at a time
        with ThreadPoolExecutor(max_workers=min(max_workers, len(scraping_tasks))) as executor:
            futures = []
            
            for platform, param in scraping_tasks:
                if platform == 'tiktok':
                    future = executor.submit(self.scrape_tiktok_hashtags, param)
                elif platform == 'amazon':
                    future = executor.submit(self.scrape_amazon_bestsellers, param)
                elif platform == 'reddit':
                    future = executor.submit(self.scrape_reddit_posts, param)
                elif platform == 'youtube':
                    future = executor.submit(self.scrape_youtube_videos, param)
                else:
                    continue
                    
                futures.append(future)
                
                # Add delay between task submissions to avoid rate limiting
                time.sleep(1)
            
            # Collect results
            for future in futures:
                try:
                    result = future.result()
                    all_data.extend(result)
                except Exception as e:
                    logger.error(f"Error in scraping task: {e}")
        
        logger.info(f"Completed scraping {len(all_data)} items from {len(scraping_tasks)} sources")
        return all_data

# If run directly, test the scraper
if __name__ == "__main__":
    scraper = ScraperEngine()
    
    # Test scraping TikTok
    print("Testing TikTok scraping...")
    tiktok_data = scraper.scrape_tiktok_hashtags()
    print(f"Found {len(tiktok_data)} TikTok hashtags")
    
    # Test scraping Amazon
    print("Testing Amazon scraping...")
    amazon_data = scraper.scrape_amazon_bestsellers()
    print(f"Found {len(amazon_data)} Amazon products")
    
    # Test scraping Reddit
    print("Testing Reddit scraping...")
    reddit_data = scraper.scrape_reddit_posts()
    print(f"Found {len(reddit_data)} Reddit posts")
    
    # Test scraping all platforms
    print("Testing multi-platform scraping...")
    all_data = scraper.scrape_all_platforms(max_workers=2)
    print(f"Found {len(all_data)} total items")