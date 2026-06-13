import logging
import os
import sys
import pandas as pd
from datetime import datetime, time as dt_time
import subprocess
import time
import pytz

# --- Add project root to sys.path ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# --- End of path addition ---

try:
    from src.screeners.screener_client import get_screener_data
    from src.newscollector.news_collector import NewsCollector
    from src.llms.llm_client import LLMClient # <-- Import LLMClient
    from src.utils.alpaca_client import AlpacaClient # <-- Import AlpacaClient
    logging.info("Successfully imported required modules.")
except ImportError as e:
    logging.error(f"Failed to import required modules: {e}")
    sys.exit(1)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - TRADEALERTS - %(levelname)s - %(message)s')

# --- Constants ---
ANALYSIS_BASE_DIR = "analysis"
import json # Add json import

NOTIFY_JSON_PATH = "src/notifications/notify.json"
EMAIL_NOTIFY_JSON_PATH = "src/notifications/email_notify.json"
# NOTIFY_SCRIPT_PATH = "src/notifications/send_notification.bat" # No longer needed
DISCORD_NOTIFIER_SCRIPT_PATH = "src/notifications/discord_notifier.py"
EMAIL_NOTIFIER_SCRIPT_PATH = "src/email/send_email.py"
DATE_FORMAT = "%Y-%m-%d"

from src.llms.llm_stock_market_client import MarketBriefingClient

# --- Load top-level config for use throughout the module ---
_CONFIG_PATH = os.path.join(project_root, 'config', 'config.json')
try:
    with open(_CONFIG_PATH, 'r') as _f:
        _GLOBAL_CONFIG = json.load(_f)
except Exception:
    _GLOBAL_CONFIG = {}

# TradingView chart ID (from config or fallback to empty string)
_TV_CHART_ID = _GLOBAL_CONFIG.get('tradingview', {}).get('chart_id', '')
_TV_COOKIES_SET = bool(_GLOBAL_CONFIG.get('tradingview', {}).get('cookies', {}).get('sessionid', ''))

def get_today_analysis_path():
    """Gets the path for today's analysis JSON file."""
    today_str = datetime.now().strftime(DATE_FORMAT)
    today_dir = os.path.join(ANALYSIS_BASE_DIR, today_str)
    os.makedirs(today_dir, exist_ok=True)
    # Change extension to .json
    return os.path.join(today_dir, "analysis.json") 

def load_processed_tickers(analysis_file_path):
    """Loads processed tickers from the daily analysis JSON file."""
    processed_data = {}
    if os.path.exists(analysis_file_path):
        try:
            with open(analysis_file_path, 'r') as f:
                processed_data = json.load(f)
            logging.info(f"Loaded {len(processed_data)} previously processed tickers from {analysis_file_path}")
        except json.JSONDecodeError:
            logging.error(f"Error decoding JSON from {analysis_file_path}. Starting fresh.")
            # Optionally backup the corrupted file here
            processed_data = {}
        except Exception as e:
            logging.error(f"Error reading analysis file {analysis_file_path}: {e}")
            processed_data = {}
    else:
        logging.info(f"Analysis file {analysis_file_path} not found. Starting fresh.")
        
    return set(processed_data.keys()) # Return only the set of tickers

def save_analysis(analysis_file_path, screener_data_df):
    """Loads existing data, updates with new data, and saves to the analysis JSON file."""
    if screener_data_df.empty:
        logging.info("No new screener data to save.")
        return
        
    # Ensure 'Ticker' column exists before proceeding
    if 'Ticker' not in screener_data_df.columns:
        logging.error("Cannot save analysis: DataFrame is missing 'Ticker' column.")
        return

    # Load existing data
    processed_data = {}
    if os.path.exists(analysis_file_path):
        try:
            with open(analysis_file_path, 'r') as f:
                processed_data = json.load(f)
            logging.info(f"Loaded {len(processed_data)} existing records from {analysis_file_path}")
        except json.JSONDecodeError:
            logging.warning(f"Could not decode existing JSON from {analysis_file_path}. Overwriting with new data.")
            processed_data = {}
        except Exception as e:
            logging.error(f"Error reading existing analysis file {analysis_file_path}: {e}. Starting fresh.")
            processed_data = {}

    # Replace NaN values with None (which becomes JSON null) before converting
    screener_data_df_cleaned = screener_data_df.where(pd.notna(screener_data_df), None)

    # Convert cleaned DataFrame data to dictionary format {ticker: {col: val, ...}}
    # Use 'records' orientation and then build the dict keyed by Ticker
    new_data_list = screener_data_df_cleaned.to_dict(orient='records')
    new_data_dict = {record['Ticker']: record for record in new_data_list if 'Ticker' in record}

    # Update existing data with new data (overwrites tickers if they reappear)
    processed_data.update(new_data_dict)
    
    # Add a timestamp for the last update
    processed_data['_last_updated'] = datetime.now().isoformat()

    # Clean the entire dictionary recursively before saving
    processed_data_cleaned = clean_value_for_json(processed_data)

    # Save cleaned data back to JSON
    try:
        with open(analysis_file_path, 'w') as f:
            json.dump(processed_data_cleaned, f, indent=4) # Use indent for readability
        # Log count based on the original processed_data before cleaning added _last_updated potentially
        log_count = len(processed_data) - 1 if '_last_updated' in processed_data else len(processed_data)
        logging.info(f"Saved/Updated {len(new_data_dict)} stocks. Total records in {analysis_file_path}: {log_count}") 
    except Exception as e:
        logging.error(f"Error writing to analysis JSON file {analysis_file_path}: {e}")


def clean_value_for_json(value):
    """Recursively cleans dict/list values for JSON compatibility (NaN, Inf -> None)."""
    if isinstance(value, dict):
        return {k: clean_value_for_json(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [clean_value_for_json(item) for item in value]
    elif isinstance(value, float):
        if pd.isna(value) or value == float('inf') or value == float('-inf'):
            return None # Convert NaN, Infinity, -Infinity to None (JSON null)
        return value
    else:
        return value

# --- LLM Output Parsing ---
def parse_llm_analysis(raw_analysis: str) -> str:
    """Removes the <think> block and surrounding whitespace from raw LLM output."""
    if not raw_analysis or not isinstance(raw_analysis, str):
        return "LLM analysis not available or invalid."

    think_end_tag = "</think>"
    think_end_index = raw_analysis.find(think_end_tag)

    if think_end_index != -1:
        analysis_part = raw_analysis[think_end_index + len(think_end_tag):]
        return analysis_part.strip()
    else:
        # If no <think> block, assume the whole output is the analysis
        # Check for common error messages from the client/model itself
        if raw_analysis.startswith("Error:") or raw_analysis.startswith("LLM analysis not available"):
             return raw_analysis # Return error messages as is
        # Otherwise, return the stripped raw analysis
        return raw_analysis.strip()


def format_large_number(num):
    """Formats large numbers into K, M, B."""
    if pd.isna(num):
        return "N/A"
    num = float(num)
    if num >= 1_000_000_000:
        return f"{num / 1_000_000_000:.2f}B"
    elif num >= 1_000_000:
        return f"{num / 1_000_000:.2f}M"
    elif num >= 1_000:
        return f"{num / 1_000:.1f}K"
    else:
        # For numbers less than 1000, decide if decimals are needed
        if num == int(num):
             return f"{int(num)}" # No decimals if whole number
        else:
             return f"{num:.2f}" # Keep decimals if present


def prepare_notification_content(new_stocks_df, llm_client: LLMClient, news_data=None):
    """
    Prepares a list of dictionaries, each representing a stock's structured data for notification,
    including LLM analysis.

    Args:
        new_stocks_df (pd.DataFrame): DataFrame containing data for new stocks.
        llm_client (LLMClient): Initialized LLM client instance.
        news_data (dict, optional): Dictionary containing news items keyed by ticker. Defaults to None.

    Returns:
        list: A list of dictionaries, where each dict contains structured info for one stock.
    """
    if new_stocks_df.empty:
        return [] # Return empty list if no new stocks
    if news_data is None:
        news_data = {}

    stock_notifications = [] # List to hold individual stock notification dicts

    # Define columns needed from the DataFrame
    notify_cols = [
        'Ticker', 'CompanyName', 'Price', 'ChangePercent', 'Volume', 'MarketCap', 'Sector', 
        'RelVolume', 'RSI', 'MACD_MACD', 'MACD_Signal',
        'Pivot_S1', 'Pivot_S2', 'Pivot_S3', 'Pivot_R1', 'Pivot_R2', 'Pivot_R3'
        # Add other desired columns like SMAs if needed, e.g., 'SMA20', 'SMA200'
    ]

    # Import screenshot service
    from src.screenshotapi.screenshot_service import take_tradingview_chart_screenshot
    
    # Initialize AlpacaClient for getting exchange information
    alpaca_client = AlpacaClient()
    
    available_cols = [col for col in notify_cols if col in new_stocks_df.columns]

    # Helper function to get current date string for screenshot directory
    def get_current_date_str():
        return datetime.now().strftime(DATE_FORMAT)

    for _, row in new_stocks_df.iterrows():
        stock_data = {} # Dictionary for the current stock
        ticker = row.get('Ticker', 'N/A')
        stock_data['ticker'] = ticker
        stock_data['company_name'] = row.get('CompanyName', 'N/A')

        # Generate TradingView chart URL and download screenshot
        chart_image_path = None # Initialize path as None
        try:
            # Get the exchange:symbol format from AlpacaClient
            exchange_symbol = row.get('Exchange')

            # Skip screenshot if TradingView chart ID not configured
            if not _TV_CHART_ID or _TV_CHART_ID == 'YOUR_TRADINGVIEW_CHART_ID':
                logging.debug(f"TradingView chart_id not configured in config.json. Skipping screenshot for {ticker}.")
            elif not _TV_COOKIES_SET:
                logging.debug(f"TradingView cookies not configured. Skipping authenticated screenshot for {ticker}.")
            else:
                chart_url = f"https://www.tradingview.com/chart/{_TV_CHART_ID}/?symbol={exchange_symbol}%3A{ticker}"
                screenshot_filename = f"{ticker}_chart"

                logging.info(f"Requesting TradingView chart for {ticker}")
                logging.info(f"Using exchange symbol: {exchange_symbol}")
                logging.info(f"Chart URL: {chart_url}")

                chart_path_obj = take_tradingview_chart_screenshot(
                    chart_url=chart_url,
                    file_name=screenshot_filename,
                    custom_date_dir=get_current_date_str()
                )

                if chart_path_obj:
                    chart_image_path = str(chart_path_obj)
                    logging.info(f"Successfully saved TradingView chart for {ticker} to {chart_image_path}")
                else:
                    logging.warning(f"Failed to download TradingView chart for {ticker} - screenshot service returned None")
        except Exception as e:
            logging.error(f"Error downloading TradingView chart for {ticker}: {e}", exc_info=True)
        
        # Add the chart path to the stock_data dictionary if it exists
        if chart_image_path:
            stock_data['chart_image_path'] = chart_image_path

        # --- Core Data ---
        core_data_lines = []
        core_cols_to_display = ['Price', 'ChangePercent', 'Volume', 'MarketCap', 'Sector', 'RelVolume'] 
        for col in core_cols_to_display:
             if col in available_cols: 
                value = row.get(col) # Use .get for safety
                value_str = "N/A" # Default
                if pd.notna(value):
                    if col in ['Volume', 'MarketCap']:
                        value_str = format_large_number(value)
                    elif col == 'ChangePercent':
                         value_str = f"{value:.2f}%"
                    elif isinstance(value, float):
                        value_str = f"{value:.2f}"
                    else:
                        value_str = str(value)
                core_data_lines.append(f"**{col}:** {value_str}")
        stock_data['core_data_str'] = "\n".join(core_data_lines) if core_data_lines else "N/A"

        # --- Technicals ---
        technicals_lines = []
        for col in ['RSI', 'MACD_MACD', 'MACD_Signal']:
            if col in available_cols:
                value = row.get(col)
                value_str = f"{value:.2f}" if isinstance(value, float) and pd.notna(value) else "N/A"
                technicals_lines.append(f"**{col}:** {value_str}")
        stock_data['technicals_str'] = "\n".join(technicals_lines) if technicals_lines else "N/A"

        # --- News ---
        stock_news_items = news_data.get(ticker, []) if news_data else []
        news_lines = []
        if stock_news_items:
            news_limit = 3 # Limit the number of news items per stock
            for idx, news_item in enumerate(stock_news_items[:news_limit]):
                title = news_item.get('title', 'N/A')
                summary = news_item.get('summary')
                # Truncate long summaries
                if summary and len(summary) > 150:
                    summary = summary[:150] + "..."
                
                news_lines.append(f"**- {title}** ({news_item.get('published_datetime', 'N/A')})")
                if summary:
                    news_lines.append(f"  {summary}") # Indent summary slightly

            if len(stock_news_items) > news_limit:
                news_lines.append(f"... (and {len(stock_news_items) - news_limit} more articles)")
        stock_data['news_str'] = "\n".join(news_lines) if news_lines else "No recent news found."

        # --- LLM Analysis ---
        parsed_analysis = "LLM analysis skipped (client not available)." # Default message
        if llm_client: # Only proceed if client is available and initialized properly
            try:
                # Prepare data dictionary for the LLM
                # Select relevant columns, handle NaN/None before passing
                llm_input_data = row[available_cols].where(pd.notna(row[available_cols]), None).to_dict()
                # Add news specifically for this ticker to the LLM input
                llm_input_data['News'] = news_data.get(ticker, []) if news_data else []
                
                # Add chart image path if available
                if 'chart_image_path' in stock_data:
                    llm_input_data['chart_image_path'] = stock_data['chart_image_path']

                logging.info(f"Requesting LLM analysis for {ticker}...")
                # Log the input data being sent to the LLM for debugging
                # logging.debug(f"LLM input data for {ticker}: {json.dumps(llm_input_data, indent=2)}") 
                raw_analysis = llm_client.analyze_stock(llm_input_data)
                # Log the raw response from the LLM client
                logging.info(f"Raw LLM analysis received for {ticker}: {raw_analysis}") 
                parsed_analysis = parse_llm_analysis(raw_analysis) # Use the helper function
                logging.info(f"Parsed LLM analysis for {ticker}: {parsed_analysis}")
                # logging.debug(f"Parsed LLM analysis for {ticker}:\n{parsed_analysis}")
            except Exception as e:
                 logging.error(f"Error during LLM analysis for {ticker}: {e}", exc_info=True)
                 parsed_analysis = f"Error during LLM analysis: {e}" # Include error in output
        else:
             logging.warning(f"LLM client not available for {ticker}, skipping analysis.")

        stock_data['llm_analysis_str'] = parsed_analysis # Assign the result or default/error message

        stock_notifications.append(stock_data) # Add the structured data for this stock

    return stock_notifications

def update_notify_json(structured_data):
    """Overwrites the notify.json and email_notify.json files with the new structured data."""
    if not structured_data:
        logging.info("No structured notification data to write.")
        for path in [NOTIFY_JSON_PATH, EMAIL_NOTIFY_JSON_PATH]:
            try:
                with open(path, 'w') as f:
                    json.dump([], f)
                logging.info(f"Cleared notification file: {path}")
            except Exception as e:
                logging.error(f"Error clearing notification file {path}: {e}")
        return

    for path in [NOTIFY_JSON_PATH, EMAIL_NOTIFY_JSON_PATH]:
        try:
            with open(path, 'w') as f:
                json.dump(structured_data, f, indent=4)
            logging.info(f"Updated notification file: {path} with {len(structured_data)} item(s).")
        except Exception as e:
            logging.error(f"Error writing to notification file {path}: {e}")

def send_notifications():
    """Executes the discord_notifier.py script directly. Email sending is handled separately."""

    # --- Check if Discord is configured ---
    discord_webhook = _GLOBAL_CONFIG.get('discord', {}).get('webhook_url', '')
    if not discord_webhook or discord_webhook in ('', 'YOUR_DISCORD_STOCK_ALERTS_WEBHOOK_URL'):
        logging.info("Discord webhook not configured. Skipping Discord notifications. "
                     "Set discord.webhook_url in config/config.json to enable.")
        return

    # --- Execute Discord Notifier ---
    if not os.path.exists(DISCORD_NOTIFIER_SCRIPT_PATH):
        logging.error(f"Discord notifier script not found: {DISCORD_NOTIFIER_SCRIPT_PATH}")
    else:
        python_executable = sys.executable 
        script_path = os.path.abspath(DISCORD_NOTIFIER_SCRIPT_PATH) 
        try:
            logging.info(f"Executing Discord notifier script: {script_path}")
            result = subprocess.run(
                [python_executable, script_path], 
                check=True, 
                capture_output=True, 
                text=True,
                cwd=project_root
            )
            logging.info("Discord notifier script executed successfully.")
            logging.info(f"Script Output:\n{result.stdout}")
            if result.stderr:
                 logging.warning(f"Script Error Output:\n{result.stderr}")
        except subprocess.CalledProcessError as e:
            logging.error(f"Discord notifier script failed with exit code {e.returncode}")
            logging.error(f"Script Output:\n{e.stdout}")
            logging.error(f"Script Error Output:\n{e.stderr}")
        except Exception as e:
            logging.error(f"Error executing Discord notifier script {script_path}: {e}")

    # Email sending is now handled exclusively by send_email_stock_alerts()


def is_market_hours():
    """
    Checks if the current time is within the defined trading hours
    (Mon-Fri, 4:00 AM to 1:00 PM PST/PDT).
    """
    # Define the Pacific Time Zone
    pacific_tz = pytz.timezone('America/Los_Angeles')
    
    # Get the current time in UTC and convert it to Pacific Time
    now_utc = datetime.now(pytz.utc)
    now_pacific = now_utc.astimezone(pacific_tz)
    
    # Define start and end times
    start_time = dt_time(4, 0)  # 4:00 AM
    end_time = dt_time(13, 0) # 1:00 PM
    
    # Define the specific delay window
    delay_start_time = dt_time(6, 30) # 6:30 AM
    delay_end_time = dt_time(6, 50)   # 6:50 AM

    # Check if it's a weekday (Monday=0, Sunday=6)
    is_weekday = now_pacific.weekday() < 5
    
    # Check if the current time is within the main trading window
    is_within_main_window = start_time <= now_pacific.time() < end_time

    # Check if the current time is within the delayed streaming window
    is_within_delay_window = delay_start_time <= now_pacific.time() < delay_end_time
    
    if not is_weekday:
        logging.info(f"Skipping cycle: It's a weekend. Current time: {now_pacific.strftime('%A, %H:%M:%S')}")
        return False
        
    if not is_within_main_window:
        logging.info(f"Skipping cycle: Outside of trading hours (4 AM - 1 PM PST). Current time: {now_pacific.strftime('%H:%M:%S')}")
        return False
    
    # If within the main window, but also within the specific delay window, return False
    if is_within_delay_window:
        logging.info(f"Skipping cycle: Within known delayed streaming period (6:30 AM - 6:50 AM PST). Current time: {now_pacific.strftime('%H:%M:%S')}")
        return False
        
    logging.info(f"Within trading hours. Proceeding with cycle. Current time: {now_pacific.strftime('%A, %H:%M:%S')}")
    return True


def is_email_enabled():
    """
    Checks if email communication is enabled in the config.
    Returns True if emails should be sent, False otherwise.
    """
    try:
        config_path = os.path.join(project_root, 'config', 'config.json')
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # Check the global send_email setting
            email_config = config.get('email', {})
            send_email = email_config.get('send_email', True)  # Default to True if not specified
            
            if not send_email:
                logging.info("Email communication is disabled in config (send_email: false)")
                return False
            
            return True
        else:
            logging.warning("Config file not found, defaulting to email enabled")
            return True
    except Exception as e:
        logging.error(f"Error reading config for email setting: {e}, defaulting to email enabled")
        return True


def send_market_briefing():
    """Checks time and sends market briefing if appropriate."""
    pacific_tz = pytz.timezone('America/Los_Angeles')
    now_pacific = datetime.now(pacific_tz)
    today_str = now_pacific.strftime(DATE_FORMAT)
    today_dir = os.path.join(ANALYSIS_BASE_DIR, today_str)
    os.makedirs(today_dir, exist_ok=True)

    # --- Define Time Windows ---
    am_start = dt_time(7, 0)
    am_end = dt_time(8, 0)
    pm_start = dt_time(12, 30)
    pm_end = dt_time(13, 0)

    # --- Determine which briefing to send ---
    briefing_type = None
    if am_start <= now_pacific.time() <= am_end:
        briefing_type = "am"
    elif pm_start <= now_pacific.time() <= pm_end:
        briefing_type = "pm"

    if not briefing_type:
        logging.info("Not within a market briefing time window.")
        return

    marker_filename = f"market_briefing_{briefing_type}_sent"
    briefing_marker_path = os.path.join(today_dir, marker_filename)

    if os.path.exists(briefing_marker_path):
        logging.info(f"Market briefing for {briefing_type.upper()} already sent today.")
        return

    logging.info(f"Time to send the {briefing_type.upper()} market briefing.")

    # --- Initialize and send briefing ---
    try:
        market_briefing_client = MarketBriefingClient()
        briefing_text = market_briefing_client.get_market_briefing()
        if briefing_text:
            briefing_notification = [{
                "title": f"Market Briefing - {now_pacific.strftime('%I:%M %p PST')}",
                "content": briefing_text
            }]
            update_notify_json(briefing_notification)
            send_notifications()

            # Also send email notification for market briefing
            if is_email_enabled():
                try:
                    from src.email.send_email import send_email_notification
                    # Prepare email content as a list with one dict item
                    email_content = [{
                        "title": f"Market Briefing - {now_pacific.strftime('%I:%M %p PST')}",
                        "content": briefing_text
                    }]
                    # Load config for email
                    config_path = os.path.join(project_root, 'config', 'config.json')
                    config = {}
                    if os.path.exists(config_path):
                        with open(config_path, 'r') as f:
                            config = json.load(f)
                    send_email_notification(config, email_content)
                    logging.info("Market briefing email sent successfully.")
                except Exception as email_exc:
                    logging.error(f"Failed to send market briefing email: {email_exc}")

            with open(briefing_marker_path, 'w') as f:
                f.write("sent")
            logging.info(f"Successfully sent {briefing_type.upper()} market briefing and marked as sent.")
        else:
            logging.warning("Market briefing text is empty. Skipping notification.")
    except Exception as e:
        logging.error(f"Failed to send market briefing: {e}")


def is_email_alert_time():
    """
    Checks if the current time is within email alert windows:
    - Morning: 7:00-8:00 AM PST (narrowed to reduce multiple sends)
    - Afternoon: 12:00-1:00 PM PST
    Returns tuple: (is_time, batch_type) where batch_type is 'morning' or 'afternoon'
    """
    pacific_tz = pytz.timezone('America/Los_Angeles')
    now_pacific = datetime.now(pacific_tz)
    
    # Define email alert time windows (morning narrowed to 30 minutes)
    morning_start = dt_time(7, 0)   # 7:00 AM
    morning_end = dt_time(8, 00)    # 7:30 AM
    afternoon_start = dt_time(12, 0) # 12:00 PM
    afternoon_end = dt_time(13, 0)   # 1:00 PM
    
    current_time = now_pacific.time()
    
    # Check if it's a weekday
    if now_pacific.weekday() >= 5:  # Saturday=5, Sunday=6
        return False, None
    
    if morning_start <= current_time <= morning_end:
        return True, 'morning'
    elif afternoon_start <= current_time <= afternoon_end:
        return True, 'afternoon'
    
    return False, None


def get_discord_notified_stocks_path(today_dir):
    """Gets the path for discord-notified-stocks.json file."""
    return os.path.join(today_dir, "discord-notified-stocks.json")


def get_email_notified_stocks_path(today_dir):
    """Gets the path for email-notified-stocks.json file."""
    return os.path.join(today_dir, "email-notified-stocks.json")


def save_discord_notified_stocks(today_dir, structured_data):
    """Saves the current structured notification data to discord-notified-stocks.json."""
    discord_file_path = get_discord_notified_stocks_path(today_dir)
    
    # Load existing data if file exists
    existing_data = []
    if os.path.exists(discord_file_path):
        try:
            with open(discord_file_path, 'r') as f:
                existing_data = json.load(f)
        except Exception as e:
            logging.error(f"Error reading existing discord notified stocks file: {e}")
            existing_data = []
    
    # Add new stocks to existing data (avoid duplicates by ticker)
    existing_tickers = {item.get('ticker') for item in existing_data if 'ticker' in item}
    new_stocks = [item for item in structured_data if 'ticker' in item and item.get('ticker') not in existing_tickers]
    
    # Also add non-stock items (like market briefings)
    non_stock_items = [item for item in structured_data if 'ticker' not in item]
    
    # Combine all data
    all_data = existing_data + new_stocks + non_stock_items
    
    try:
        with open(discord_file_path, 'w') as f:
            json.dump(all_data, f, indent=4)
        logging.info(f"Saved {len(new_stocks)} new stocks to discord-notified-stocks.json. Total: {len(all_data)}")
    except Exception as e:
        logging.error(f"Error saving discord notified stocks file: {e}")


def load_discord_notified_stocks(today_dir):
    """Loads all stocks from discord-notified-stocks.json."""
    discord_file_path = get_discord_notified_stocks_path(today_dir)
    
    if not os.path.exists(discord_file_path):
        return []
    
    try:
        with open(discord_file_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Error loading discord notified stocks file: {e}")
        return []


def load_email_notified_stocks(today_dir):
    """Loads stocks that have already been sent via email."""
    email_file_path = get_email_notified_stocks_path(today_dir)
    
    if not os.path.exists(email_file_path):
        return []
    
    try:
        with open(email_file_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Error loading email notified stocks file: {e}")
        return []


def save_email_notified_stocks(today_dir, stocks_data):
    """Saves stocks that have been sent via email to email-notified-stocks.json."""
    email_file_path = get_email_notified_stocks_path(today_dir)
    
    try:
        with open(email_file_path, 'w') as f:
            json.dump(stocks_data, f, indent=4)
        logging.info(f"Saved {len(stocks_data)} stocks to email-notified-stocks.json")
    except Exception as e:
        logging.error(f"Error saving email notified stocks file: {e}")


def get_new_stocks_for_email(today_dir, batch_type):
    """
    Gets stocks that should be sent in the current email batch.
    For morning batch: all stocks collected so far
    For afternoon batch: only new stocks not sent in morning batch
    """
    discord_stocks = load_discord_notified_stocks(today_dir)
    
    if batch_type == 'morning':
        # Morning batch: send all stocks collected so far
        stock_items = [item for item in discord_stocks if 'ticker' in item]
        logging.info(f"Morning batch: Found {len(stock_items)} stocks to send")
        return stock_items
    
    elif batch_type == 'afternoon':
        # Afternoon batch: only send new stocks not already emailed
        email_notified_stocks = load_email_notified_stocks(today_dir)
        email_notified_tickers = {item.get('ticker') for item in email_notified_stocks if 'ticker' in item}
        
        # Get only stock items from discord that haven't been emailed
        new_stock_items = [
            item for item in discord_stocks 
            if 'ticker' in item and item.get('ticker') not in email_notified_tickers
        ]
        
        logging.info(f"Afternoon batch: Found {len(new_stock_items)} new stocks to send (out of {len(discord_stocks)} total)")
        return new_stock_items
    
    return []


def send_email_stock_alerts():
    """
    Checks if it's time to send email stock alerts and sends them if appropriate.
    Handles both morning (7-8:00 AM) and afternoon (12-1 PM) batches.
    """
    # Check if email is globally enabled
    if not is_email_enabled():
        return  # Email is disabled, skip all email operations
    
    is_time, batch_type = is_email_alert_time()
    
    if not is_time:
        return  # Not time for email alerts
    
    pacific_tz = pytz.timezone('America/Los_Angeles')
    now_pacific = datetime.now(pacific_tz)
    today_str = now_pacific.strftime(DATE_FORMAT)
    today_dir = os.path.join(ANALYSIS_BASE_DIR, today_str)
    os.makedirs(today_dir, exist_ok=True)
    
    # Check if this batch has already been sent
    email_marker_path = os.path.join(today_dir, f"email_stocks_{batch_type}_sent")
    if os.path.exists(email_marker_path):
        logging.info(f"Email stock alerts for {batch_type} batch already sent today. Marker path: {email_marker_path}")
        return
    
    logging.info(f"Time to send {batch_type} email stock alerts batch. Marker path: {email_marker_path}")
    
    # Double-check marker file existence immediately before sending
    if os.path.exists(email_marker_path):
        logging.info(f"Marker file found again before sending. Skipping duplicate send. Marker path: {email_marker_path}")
        return
    
    # Get stocks for this batch
    stocks_to_email = get_new_stocks_for_email(today_dir, batch_type)
    
    if not stocks_to_email:
        logging.info(f"No new stocks to send in {batch_type} batch.")
        return
    
    # Create email notification using existing email system
    try:
        # Load config for email
        config_path = os.path.join(project_root, 'config', 'config.json')
        config = {}
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = json.load(f)
        
        # Import email function
        from src.email.send_email import send_email_notification
        
        # Send email with stock cards
        send_email_notification(config, stocks_to_email)
        
        # Update email-notified-stocks.json with all stocks sent so far
        if batch_type == 'morning':
            # For morning batch, save all stocks sent
            save_email_notified_stocks(today_dir, stocks_to_email)
        else:
            # For afternoon batch, add new stocks to existing list
            existing_email_stocks = load_email_notified_stocks(today_dir)
            all_emailed_stocks = existing_email_stocks + stocks_to_email
            save_email_notified_stocks(today_dir, all_emailed_stocks)
        
        # Mark this batch as sent
        with open(email_marker_path, 'w') as f:
            f.write("sent")
        
        logging.info(f"Successfully sent {batch_type} email batch with {len(stocks_to_email)} stocks and marked as sent.")
        
    except Exception as e:
        logging.error(f"Failed to send {batch_type} email stock alerts: {e}")


def main():
    """Main execution function."""
    logging.info("--- Starting Trade Alerts Script ---")

    # Get today's directory for state files
    pacific_tz = pytz.timezone('America/Los_Angeles')
    now_pacific = datetime.now(pacific_tz)
    today_str = now_pacific.strftime(DATE_FORMAT)
    today_dir = os.path.join(ANALYSIS_BASE_DIR, today_str)
    os.makedirs(today_dir, exist_ok=True)

    # --- Check if within market hours for stock alerts ---
    if not is_market_hours():
        logging.info("Outside of market hours for continuous stock alerts. Ending cycle.")
        return
    
    # --- Send Market Briefing if applicable ---
    send_market_briefing()

    # --- Check and send email stock alerts if applicable ---
    send_email_stock_alerts()

    # --- Initialize LLM Client ---
    try:
        # Assuming config.json is in the standard location relative to project root
        config_path = os.path.join(project_root, 'config', 'config.json')
        llm_client = LLMClient(config_path=config_path)
        if not llm_client.model or not llm_client.prompt_template:
             logging.warning("LLMClient initialized but model or prompt might be missing. Analysis may fail.")
             # Decide if this should be a fatal error or just a warning
             # For now, let it continue but log a warning.
    except Exception as e:
        logging.error(f"Failed to initialize LLMClient: {e}. LLM analysis will be skipped.", exc_info=True)
        llm_client = None # Ensure llm_client is None if initialization fails

    # 1. Get screener data
    logging.info("Fetching screener data...")
    screener_data_df = get_screener_data()

    if screener_data_df is None or screener_data_df.empty:
        logging.warning("No data received from screener. Exiting.")
        return

    logging.info(f"Received {len(screener_data_df)} stocks from screener.")
    # Ensure 'Ticker' column exists
    if 'Ticker' not in screener_data_df.columns:
        logging.error("Screener data is missing the required 'Ticker' column. Exiting.")
        return

    # 2. Handle analysis file
    analysis_file_path = get_today_analysis_path()
    processed_tickers = load_processed_tickers(analysis_file_path)
    save_analysis(analysis_file_path, screener_data_df) # Save all current results

    # 3. Identify new stocks for news and notification
    current_tickers = set(screener_data_df['Ticker'])
    new_tickers_list = list(current_tickers - processed_tickers)
    logging.info(f"Found {len(new_tickers_list)} new tickers for news/notification: {new_tickers_list}")

    # Filter DataFrame for new stocks
    new_stocks_df = screener_data_df[screener_data_df['Ticker'].isin(new_tickers_list)].copy()

    # 4. Collect news for new stocks
    if new_tickers_list:
        logging.info("Collecting news for new tickers...")
        try:
            news_collector = NewsCollector() # Assumes default config path is okay
            # The collect_news method handles its own output/logging based on its implementation
            news_results = news_collector.collect_news(new_tickers_list)
            # Optional: Log summary of news collection if needed
            logging.info(f"News collection process initiated for {len(new_tickers_list)} tickers. Results logged by NewsCollector.")
            # logging.debug(f"News results structure: {news_results}") # Uncomment for debugging news output
        except Exception as e:
            logging.error(f"Error during news collection: {e}")
            news_results = {}
    else:
        logging.info("No new tickers to fetch news for.")
        news_results = {}

    # 5. Prepare and send notifications for new stocks
    if not new_stocks_df.empty:
        logging.info("Preparing notification content...")
        # Pass llm_client and news_results to the notification preparation function
        if llm_client:
            structured_notification_data = prepare_notification_content(
                new_stocks_df,
                llm_client, # Pass the initialized client
                news_results if new_tickers_list else {}
            )
        else:
            # Fallback if LLM client failed to initialize - skip LLM analysis
            logging.warning("LLMClient not available, preparing notification without LLM analysis.")
            structured_notification_data = prepare_notification_content(
                new_stocks_df,
                None, # Pass None explicitly
                news_results if new_tickers_list else {}
            )

        if structured_notification_data:
            # Save to discord-notified-stocks.json for email batching
            save_discord_notified_stocks(today_dir, structured_notification_data)
            
            # Send regular Discord notifications
            update_notify_json(structured_notification_data) # Call the new JSON update function
            send_notifications()
        else:
            logging.info("No notification data generated.")
            update_notify_json([]) # Ensure notify.json is cleared if no new stocks
    else:
        logging.info("No new stocks found for notification in this cycle. Will try again in 15 min.")

    logging.info("--- Trade Alerts Cycle Finished ---")


if __name__ == "__main__":
    while True:
        try:
            main()
        except Exception as e:
            logging.error(f"An unexpected error occurred in the main loop: {e}")
            logging.error("Restarting loop after a short delay...")
            time.sleep(60) # Wait 1 minute before restarting after a major error
        
        logging.info("Waiting 15 minutes for the next cycle...")
        time.sleep(900) # Sleep for 15 minutes (15 * 60 seconds)
