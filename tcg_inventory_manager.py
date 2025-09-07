import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import requests
import time
from datetime import datetime
import json
import hashlib
import os
from typing import Dict, List, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TCGInventoryManager:
    """Manages trading card inventory synchronization between Manabox and Google Sheets"""
    
    def __init__(self, google_credentials_path: str, tcgplayer_api_key: str = None):
        """
        Initialize the inventory manager
        
        Args:
            google_credentials_path: Path to Google service account JSON credentials
            tcgplayer_api_key: Optional TCGPlayer API key for price data
        """
        self.setup_google_sheets(google_credentials_path)
        self.tcgplayer_api_key = tcgplayer_api_key
        self.price_cache = {}
        self.cache_duration = 3600  # Cache prices for 1 hour
        
    def setup_google_sheets(self, credentials_path: str):
        """Setup Google Sheets API connection"""
        scope = ['https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive']
        
        creds = Credentials.from_service_account_file(credentials_path, scopes=scope)
        self.gc = gspread.authorize(creds)
        
    def import_manabox_csv(self, csv_path: str) -> pd.DataFrame:
        """
        Import Manabox CSV export
        
        Args:
            csv_path: Path to Manabox CSV export file
            
        Returns:
            DataFrame with card inventory data
        """
        try:
            # Read Manabox CSV (adjust column names based on actual export format)
            df = pd.read_csv(csv_path)
            
            # Standardize column names
            column_mapping = {
                'Name': 'card_name',
                'Set': 'set_name',
                'Set Code': 'set_code',
                'Collector Number': 'collector_number',
                'Quantity': 'quantity',
                'Foil': 'is_foil',
                'Condition': 'condition',
                'Language': 'language',
                'Purchase Price': 'purchase_price'
            }
            
            df = df.rename(columns=column_mapping)
            
            # Add timestamp
            df['last_updated'] = datetime.now().isoformat()
            
            logger.info(f"Imported {len(df)} cards from Manabox CSV")
            return df
            
        except Exception as e:
            logger.error(f"Error importing Manabox CSV: {e}")
            raise
            
    def fetch_scryfall_prices(self, card_name: str, set_code: str = None) -> Dict:
        """
        Fetch card prices from Scryfall API (free, no key required)
        
        Args:
            card_name: Name of the card
            set_code: Optional set code for specific printing
            
        Returns:
            Dictionary with price data
        """
        # Check cache first
        cache_key = f"{card_name}_{set_code}"
        if cache_key in self.price_cache:
            cached_data = self.price_cache[cache_key]
            if time.time() - cached_data['timestamp'] < self.cache_duration:
                return cached_data['prices']
        
        try:
            # Build Scryfall API query
            base_url = "https://api.scryfall.com/cards/named"
            params = {
                'fuzzy': card_name,
                'format': 'json'
            }
            
            if set_code:
                params['set'] = set_code.lower()
            
            response = requests.get(base_url, params=params)
            
            # Rate limiting (Scryfall allows 10 requests per second)
            time.sleep(0.1)
            
            if response.status_code == 200:
                data = response.json()
                prices = {
                    'usd': data.get('prices', {}).get('usd', 0),
                    'usd_foil': data.get('prices', {}).get('usd_foil', 0),
                    'eur': data.get('prices', {}).get('eur', 0),
                    'tix': data.get('prices', {}).get('tix', 0),
                    'market_url': data.get('purchase_uris', {}).get('tcgplayer', ''),
                    'image_url': data.get('image_uris', {}).get('normal', '')
                }
                
                # Cache the result
                self.price_cache[cache_key] = {
                    'prices': prices,
                    'timestamp': time.time()
                }
                
                return prices
            else:
                logger.warning(f"Could not fetch price for {card_name}: {response.status_code}")
                return {'usd': 0, 'usd_foil': 0}
                
        except Exception as e:
            logger.error(f"Error fetching price for {card_name}: {e}")
            return {'usd': 0, 'usd_foil': 0}
            
    def update_prices_in_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Update DataFrame with current market prices
        
        Args:
            df: DataFrame with card inventory
            
        Returns:
            DataFrame with updated price columns
        """
        df['current_price'] = 0.0
        df['price_change'] = 0.0
        df['total_value'] = 0.0
        df['market_url'] = ''
        
        for idx, row in df.iterrows():
            prices = self.fetch_scryfall_prices(
                row['card_name'], 
                row.get('set_code', None)
            )
            
            # Determine which price to use based on foil status
            if row.get('is_foil', False):
                current_price = float(prices.get('usd_foil', 0) or 0)
            else:
                current_price = float(prices.get('usd', 0) or 0)
            
            df.at[idx, 'current_price'] = current_price
            df.at[idx, 'total_value'] = current_price * row.get('quantity', 1)
            
            # Calculate price change if purchase price exists
            if 'purchase_price' in row and row['purchase_price']:
                df.at[idx, 'price_change'] = current_price - float(row['purchase_price'])
            
            df.at[idx, 'market_url'] = prices.get('market_url', '')
            
            # Log progress every 10 cards
            if (idx + 1) % 10 == 0:
                logger.info(f"Updated prices for {idx + 1}/{len(df)} cards")
        
        # Add summary statistics
        df['price_last_updated'] = datetime.now().isoformat()
        
        return df
        
    def update_google_sheet(self, df: pd.DataFrame, spreadsheet_name: str, 
                           worksheet_name: str = 'Inventory'):
        """
        Update Google Sheets with inventory data
        
        Args:
            df: DataFrame with inventory and price data
            spreadsheet_name: Name of the Google Spreadsheet
            worksheet_name: Name of the worksheet tab
        """
        try:
            # Open or create spreadsheet
            try:
                sheet = self.gc.open(spreadsheet_name)
            except gspread.SpreadsheetNotFound:
                sheet = self.gc.create(spreadsheet_name)
                sheet.share('your-email@example.com', perm_type='user', role='owner')
                logger.info(f"Created new spreadsheet: {spreadsheet_name}")
            
            # Get or create worksheet
            try:
                worksheet = sheet.worksheet(worksheet_name)
                worksheet.clear()
            except gspread.WorksheetNotFound:
                worksheet = sheet.add_worksheet(title=worksheet_name, rows=len(df)+100, cols=20)
            
            # Prepare data for upload
            headers = df.columns.tolist()
            values = df.values.tolist()
            
            # Update headers
            worksheet.update('A1', [headers])
            
            # Update data
            if values:
                worksheet.update(f'A2:Z{len(values)+1}', values)
            
            # Format the sheet
            self.format_google_sheet(worksheet, len(df))
            
            # Add summary sheet
            self.create_summary_sheet(sheet, df)
            
            logger.info(f"Successfully updated Google Sheet: {spreadsheet_name}")
            
        except Exception as e:
            logger.error(f"Error updating Google Sheet: {e}")
            raise
            
    def format_google_sheet(self, worksheet, num_rows: int):
        """Apply formatting to the Google Sheet"""
        try:
            # Format header row
            worksheet.format('A1:Z1', {
                'backgroundColor': {'red': 0.2, 'green': 0.2, 'blue': 0.2},
                'textFormat': {'bold': True, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}},
                'horizontalAlignment': 'CENTER'
            })
            
            # Format price columns as currency
            price_columns = ['H', 'I', 'J']  # Adjust based on your column layout
            for col in price_columns:
                worksheet.format(f'{col}2:{col}{num_rows+1}', {
                    'numberFormat': {'type': 'CURRENCY', 'pattern': '$#,##0.00'}
                })
            
            # Add conditional formatting for price changes
            # Positive changes in green, negative in red
            worksheet.format('J2:J', {
                'conditionalFormatRules': [{
                    'ranges': [{'sheetId': worksheet.id, 'startColumnIndex': 9, 'endColumnIndex': 10}],
                    'booleanRule': {
                        'condition': {'type': 'NUMBER_GREATER', 'values': [{'userEnteredValue': '0'}]},
                        'format': {'backgroundColor': {'red': 0.8, 'green': 1, 'blue': 0.8}}
                    }
                }]
            })
            
        except Exception as e:
            logger.warning(f"Could not apply formatting: {e}")
            
    def create_summary_sheet(self, spreadsheet, df: pd.DataFrame):
        """Create a summary dashboard sheet"""
        try:
            # Get or create summary worksheet
            try:
                summary = spreadsheet.worksheet('Summary')
                summary.clear()
            except gspread.WorksheetNotFound:
                summary = spreadsheet.add_worksheet(title='Summary', rows=50, cols=10)
            
            # Calculate summary statistics
            total_cards = len(df)
            total_quantity = df['quantity'].sum()
            total_value = df['total_value'].sum()
            avg_card_value = df['current_price'].mean()
            
            # Top 10 most valuable cards
            top_cards = df.nlargest(10, 'total_value')[['card_name', 'set_name', 'quantity', 'total_value']]
            
            # Create summary data
            summary_data = [
                ['Trading Card Inventory Summary'],
                ['Last Updated:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
                [''],
                ['Total Unique Cards:', total_cards],
                ['Total Card Quantity:', total_quantity],
                ['Total Collection Value:', f'${total_value:,.2f}'],
                ['Average Card Value:', f'${avg_card_value:,.2f}'],
                [''],
                ['Top 10 Most Valuable Cards:'],
                ['Card Name', 'Set', 'Quantity', 'Total Value']
            ]
            
            # Add top cards to summary
            for _, card in top_cards.iterrows():
                summary_data.append([
                    card['card_name'],
                    card['set_name'],
                    card['quantity'],
                    f'${card["total_value"]:,.2f}'
                ])
            
            # Update summary sheet
            summary.update('A1', summary_data)
            
            # Format summary sheet
            summary.format('A1:D1', {
                'textFormat': {'bold': True, 'fontSize': 14},
                'horizontalAlignment': 'CENTER'
            })
            
            logger.info("Created summary dashboard")
            
        except Exception as e:
            logger.warning(f"Could not create summary sheet: {e}")
            
    def run_sync(self, csv_path: str, spreadsheet_name: str):
        """
        Run a complete synchronization cycle
        
        Args:
            csv_path: Path to Manabox CSV export
            spreadsheet_name: Name of Google Spreadsheet to update
        """
        logger.info("Starting inventory synchronization...")
        
        # Import Manabox data
        df = self.import_manabox_csv(csv_path)
        
        # Update with current prices
        df = self.update_prices_in_dataframe(df)
        
        # Update Google Sheets
        self.update_google_sheet(df, spreadsheet_name)
        
        logger.info("Synchronization complete!")
        
        # Return summary statistics
        return {
            'total_cards': len(df),
            'total_value': df['total_value'].sum(),
            'last_updated': datetime.now().isoformat()
        }

# Example usage and automation script
def main():
    """Main execution function"""
    
    # Configuration
    GOOGLE_CREDS_PATH = 'path/to/google-credentials.json'
    MANABOX_CSV_PATH = r'c:\Users\grand\Downloads\Collection (1).csv'
    SPREADSHEET_NAME = 'TCG Inventory Tracker'
    
    # Initialize manager
    manager = TCGInventoryManager(
        google_credentials_path=GOOGLE_CREDS_PATH
    )
    
    # Run synchronization
    results = manager.run_sync(MANABOX_CSV_PATH, SPREADSHEET_NAME)
    
    print(f"Sync complete! Total value: ${results['total_value']:,.2f}")

# Automation with schedule (optional)
def run_automated():
    """Run automated synchronization on a schedule"""
    import schedule
    
    def sync_job():
        try:
            main()
        except Exception as e:
            logger.error(f"Sync failed: {e}")
    
    # Schedule to run every hour
    schedule.every(1).hours.do(sync_job)
    
    # Keep running
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()