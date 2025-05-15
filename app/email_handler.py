
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)
class EmailHandler:
    def __init__(self):
        # Load email credentials from environment variables
        self.email_user = os.getenv("EMAIL_USER")
        self.email_password = os.getenv("EMAIL_APP_PASSWORD")  # App password for Gmail
        self.email_server = os.getenv("EMAIL_SERVER", "smtp.gmail.com")
        self.email_port = int(os.getenv("EMAIL_PORT", "587"))
        self.recipient_email = os.getenv("RECIPIENT_EMAIL")
        
    def send_trade_notification(self, trades):
        """Send notification email about executed trades"""
        subject = f"Stock Bot: Trade Notification"
        
        # Create message body with trade details
        title = f"""
        <h2>Trade Notification</h2>
        <p>Your Stock Bot has executed the following trade:</p>
        """
        message = ""
        for trade_info in trades:
            contract_symbol = trade_info.get('contract_symbol')
            ticker = trade_info.get('ticker')
            type = trade_info.get('type')
            premium = trade_info.get('premium')
            quantity = trade_info.get('quantity')
            exit_premium = trade_info.get('exit_premium')
            stop_loss = trade_info.get('stop_loss')
            total_cost = trade_info.get('total_cost')
            total_profit = trade_info.get('total_profit')
            total_loss = trade_info.get('total_loss')
            trade = f"""
                <ul>
                    <li><strong>Symbol:</strong> {ticker}</li>
                    <li><strong>Contract:</strong> {contract_symbol}</li>
                    <li><strong>Type:</strong> {type}</li>
                    <li><strong>Premium per Contract:</strong> ${premium}</li>
                    <li><strong>Exit Premium:</strong> ${exit_premium}</li>
                    <li><strong>Stop Loss:</strong> ${stop_loss}</li>
                    <li><strong>Quantity:</strong> {quantity}</li>
                    <h2><strong>Possible Total Cost:</strong> ${total_cost}</h2>
                    <h2><strong>Possible Total Profit:</strong><span style="color: green;"> ${total_profit}</span></h2>
                    <h2><strong>Acceptable Total Loss:</strong><span style="color: red;"> ${total_loss}</span></h2>
                    <hr style="border-top: 3px solid #bbb;">
                </ul>
                """
            message += trade
        
        body = f"{title}\n{message}"
        
        self.send_email(subject, body, is_html=True)
    
    def send_error_notification(self, error_message):
        """Send notification about errors in the trading system"""
        subject = f"Stock Bot: ERROR ALERT"
        body = f"Your Stock Bot encountered an error:\n\n{error_message}"
        self.send_email(subject, body)
        
    def send_schedule_notification(self, next_run_time):
        """Send notification about the next scheduled trading window"""
        subject = f"Stock Bot: Schedule Update"
        body = f"Your Stock Bot will next run at: {next_run_time}"
        self._send_email(subject, body)
        
    def send_email(self, subject, body, is_html=False):
        try:
            # Check if credentials are available
            if not self.email_user or not self.email_password or not self.recipient_email:
                logger.error("Email credentials not configured. Cannot send notification.")
                return False
                
            # Create message
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = self.email_user
            message["To"] = self.recipient_email
            
            # Attach body as plain text or HTML
            if is_html:
                message.attach(MIMEText(body, "html"))
            else:
                message.attach(MIMEText(body, "plain"))
            
            # Connect to server and send
            with smtplib.SMTP(self.email_server, self.email_port) as server:
                server.starttls()  # Secure the connection
                server.login(self.email_user, self.email_password)
                server.send_message(message)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")
            return False