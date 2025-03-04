"""
Niche Researcher - Trend Analyzer
Data processing logic for analyzing market trends and niche opportunities
"""

import os
import yaml
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pytrends.request import TrendReq
import importlib
import importlib.util
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('trend_analyzer')

# Load configuration
try:
    with open('config.yaml', 'r') as config_file:
        config = yaml.safe_load(config_file)
except Exception as e:
    logger.error(f"Error loading configuration: {e}")
    config = {}

# Default affiliate program database
AFFILIATE_DB = {
    'AI Tools': ['Jasper', 'Copy.ai', 'WriteSonic', 'Notion AI'],
    'Fitness': ['Bodybuilding.com', 'MyProtein', 'Gymshark', 'Rogue Fitness'],
    'Home Automation': ['Amazon Associates', 'SmartThings', 'Philips Hue', 'Nest'],
    'Pet Products': ['Chewy', 'Petco', 'Amazon Associates', 'PetSmart'],
    'Sustainable Living': ['EarthHero', 'Public Goods', 'Thrive Market', 'Avocado Green Mattress'],
    'Remote Work': ['FlexJobs', 'Autonomous', 'Amazon Associates', 'Udemy'],
    'Beauty': ['Sephora', 'Ulta', 'Fenty Beauty', 'Glossier'],
    'Financial Tools': ['Robinhood', 'Acorns', 'Personal Capital', 'Credit Karma'],
    'Digital Art': ['Skillshare', 'Domestika', 'Wacom', 'Creative Market'],
    'Mental Health': ['BetterHelp', 'Headspace', 'Calm', 'Talkspace'],
    'Gaming': ['Razer', 'Logitech', 'SteelSeries', 'G2A'],
    'Outdoor Gear': ['REI', 'Backcountry', 'Columbia', 'The North Face'],
    'Smart Home': ['Amazon Associates', 'Best Buy', 'Home Depot', 'Lowe\'s'],
    'Baby Products': ['Amazon Associates', 'Target', 'BuyBuyBaby', 'Carter\'s'],
    'Cooking': ['Sur La Table', 'Williams Sonoma', 'Blue Apron', 'HelloFresh'],
    'Language Learning': ['Babbel', 'Rosetta Stone', 'Duolingo', 'Preply'],
    'Travel Gear': ['Amazon Associates', 'Eagle Creek', 'Samsonite', 'TravelPro'],
    'Home Office': ['Fully', 'Herman Miller', 'Autonomous', 'Steelcase'],
    'Solar Products': ['Goal Zero', 'Jackery', 'Renogy', 'EcoFlow'],
    'AI Pet Tech': ['Petcube', 'Chewy', 'Furbo', 'Whistle'],
    'Wireless Earbuds': ['Amazon Associates', 'Best Buy', 'JBL', 'Bose'],
    'Streaming Services': ['Netflix', 'Disney+', 'Hulu', 'HBO Max'],
    'Plant Care': ['The Sill', 'Bloomscape', 'Amazon Associates', 'Plant Therapy'],
    'Eco-Friendly Beauty': ['Beautycounter', 'Credo Beauty', 'The Detox Market', 'ILIA Beauty'],
    'Smart Fitness': ['Peloton', 'Mirror', 'Echelon', 'NordicTrack']
}

# Content strategy templates
CONTENT_STRATEGY_TEMPLATES = {
    'TikTok': [
        "{niche} product comparison", 
        "{niche} DIY hacks", 
        "{niche} unboxing review",
        "Day in the life with {niche}",
        "Before and after {niche} transformation"
    ],
    'YouTube': [
        "{niche} beginner guide", 
        "Best {niche} products 2025", 
        "{niche} in-depth review",
        "How I made money with {niche}",
        "{niche} tutorial for beginners"
    ],
    'Blog': [
        "10 best {niche} products worth buying", 
        "How to get started with {niche}", 
        "{niche} buyer's guide",
        "{niche} mistakes to avoid",
        "Ultimate {niche} comparison"
    ],
    'Instagram': [
        "{niche} transformation post", 
        "{niche} daily tips", 
        "{niche} product highlight",
        "{niche} before/after carousel",
        "{niche} tutorial reels"
    ],
    'Pinterest': [
        "{niche} inspiration board", 
        "{niche} step-by-step guide", 
        "{niche} buying guide",
        "{niche} DIY infographic",
        "How to choose the best {niche}"
    ]
}

class TrendAnalyzer:
    """Analyzes market trends and identifies niche opportunities"""
    
    def __init__(self, scraped_data=None):
        self.trend_config = config.get('trend_analysis', {})
        self.growth_weight = self.trend_config.get('growth_weight', 0.7)
        self.competition_weight = self.trend_config.get('competition_weight', 0.3)
        self.min_growth_percentage = self.trend_config.get('min_growth_percentage', 15)
        self.date_range = self.trend_config.get('date_range', '6mo')
        
        self.affiliate_db = AFFILIATE_DB.copy()
        self.scraped_data = scraped_data or []
        self.trend_data = None
        self.niche_scores = None
        
        # Load custom plugins if available
        self._load_plugins()
        
    def _load_plugins(self):
        """Load custom plugins for affiliate networks and scoring algorithms"""
        plugins_config = config.get('plugins', {})
        if not plugins_config.get('enabled', False):
            return
            
        plugin_dir = plugins_config.get('directory', 'plugins')
        if not os.path.exists(plugin_dir):
            logger.info(f"Plugin directory {plugin_dir} does not exist. Skipping plugin loading.")
            return
            
        # Load affiliate network plugins
        affiliate_networks = plugins_config.get('affiliate_networks', [])
        for network in affiliate_networks:
            if network.get('enabled', False):
                plugin_name = network.get('name')
                try:
                    # Attempt to load the plugin
                    plugin_path = os.path.join(plugin_dir, f"{plugin_name}.py")
                    if os.path.exists(plugin_path):
                        spec = importlib.util.spec_from_file_location(plugin_name, plugin_path)
                        plugin_module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(plugin_module)
                        
                        # Add affiliate programs from plugin
                        if hasattr(plugin_module, 'AFFILIATE_PROGRAMS'):
                            self.affiliate_db.update(plugin_module.AFFILIATE_PROGRAMS)
                            logger.info(f"Loaded affiliate programs from {plugin_name}")
                except Exception as e:
                    logger.error(f"Error loading affiliate network plugin {plugin_name}: {e}")
    
    def fetch_google_trends(self, keywords, timeframe='6-m'):
        """Fetch trend data from Google Trends"""
        logger.info(f"Fetching Google Trends data for {len(keywords)} keywords")
        
        # Convert timeframe from config format to pytrends format
        if timeframe == '6mo' or timeframe == '6-m':
            timeframe = 'today 6-m'
        elif timeframe == '12mo' or timeframe == '12-m':
            timeframe = 'today 12-m'
        elif timeframe == '3mo' or timeframe == '3-m':
            timeframe = 'today 3-m'
        else:
            timeframe = 'today 6-m'  # Default to 6 months
            
        try:
            pytrends = TrendReq(timeout=config.get('apis', {}).get('pytrends', {}).get('timeout', 60))
            
            #