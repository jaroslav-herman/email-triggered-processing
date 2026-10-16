#!/usr/bin/env python3
"""
Email-triggered local data processing for electrochemical data

Polls a shared lab Gmail account for instruction emails (subject starting with [RUN]),
executes attached processing code with local data, and emails results back.

Usage:
    python processor.py [--config CONFIG_FILE] [--once] [--verbose]

Options:
    --config    Path to config file (default: config/gmail_config.json)
    --once      Run once and exit (don't loop)
    --verbose   Enable verbose logging
"""

import argparse
import email
import imaplib
import json
import logging
import os
import smtplib
import sys
import tempfile
import time
import traceback
from datetime import datetime
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Dict, Any, Optional

# Configure logging
# Ensure logs directory exists
os.makedirs('logs', exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/processor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class GmailProcessor:
    """Main processor class for handling email-triggered processing."""
    
    SUBJECT_PREFIX = "[RUN]"
    PROCESSED_LABEL = "PROCESSED"
    ERROR_LABEL = "ERROR"
    MAX_ATTACHMENT_SIZE = 25 * 1024 * 1024  # 25 MB
    POLL_INTERVAL = 60  # seconds
    
    def __init__(self, config_path: str = "config/gmail_config.json"):
        """Initialize the processor with configuration."""
        self.config_path = config_path
        self.config = self._load_config()
        self.imap_server = None
        self.smtp_server = None
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file."""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            
            # Validate required fields
            required = ['imap_server', 'imap_port', 'smtp_server', 'smtp_port', 
                       'username', 'password', 'data_dir']
            for field in required:
                if field not in config:
                    raise ValueError(f"Missing required config field: {field}")
            
            return config
        except FileNotFoundError:
            logger.error(f"Config file not found: {self.config_path}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file: {e}")
            raise
        except ValueError as e:
            logger.error(f"Invalid config: {e}")
            raise
    
    def connect_imap(self) -> imaplib.IMAP4_SSL:
        """Connect to IMAP server."""
        try:
            self.imap_server = imaplib.IMAP4_SSL(
                self.config['imap_server'],
                self.config['imap_port']
            )
            self.imap_server.login(
                self.config['username'],
                self.config['password']
            )
            logger.info("Connected to IMAP server")
            return self.imap_server
        except Exception as e:
            logger.error(f"IMAP connection failed: {e}")
            raise
    
    def connect_smtp(self) -> smtplib.SMTP:
        """Connect to SMTP server."""
        try:
            self.smtp_server = smtplib.SMTP(
                self.config['smtp_server'],
                self.config['smtp_port']
            )
            self.smtp_server.starttls()
            self.smtp_server.login(
                self.config['username'],
                self.config['password']
            )
            logger.info("Connected to SMTP server")
            return self.smtp_server
        except Exception as e:
            logger.error(f"SMTP connection failed: {e}")
            raise
    
    def disconnect_imap(self):
        """Disconnect from IMAP server."""
        if self.imap_server:
            try:
                self.imap_server.close()
                self.imap_server.logout()
                logger.info("Disconnected from IMAP server")
            except Exception as e:
                logger.error(f"IMAP disconnect error: {e}")
            self.imap_server = None
    
    def disconnect_smtp(self):
        """Disconnect from SMTP server."""
        if self.smtp_server:
            try:
                self.smtp_server.quit()
                logger.info("Disconnected from SMTP server")
            except Exception as e:
                logger.error(f"SMTP disconnect error: {e}")
            self.smtp_server = None
    
    def _ensure_labels(self):
        """Ensure required labels exist."""
        try:
            # List existing labels
            status, labels = self.imap_server.list()
            existing = [label.decode().split(' "/" ')[1] for label in labels if b'\\Noselect' not in label]
            
            # Create missing labels
            for label in [self.PROCESSED_LABEL, self.ERROR_LABEL]:
                if label not in existing:
                    self.imap_server.create(f'"{label}"')
                    logger.info(f"Created label: {label}")
        except Exception as e:
            logger.error(f"Failed to ensure labels: {e}")
    
    def find_instruction_emails(self) -> List[str]:
        """Find unread emails with [RUN] prefix in subject."""
        try:
            self.imap_server.select('INBOX')
            
            # Search for unread emails with [RUN] in subject
            status, messages = self.imap_server.search(
                None,
                f'(UNSEEN SUBJECT "{self.SUBJECT_PREFIX}")'
            )
            
            if status != 'OK':
                logger.error("IMAP search failed")
                return []
            
            email_ids = messages[0].split()
            logger.info(f"Found {len(email_ids)} instruction emails")
            return email_ids
            
        except Exception as e:
            logger.error(f"Error finding instruction emails: {e}")
            return []
    
    def parse_email(self, email_id: str) -> Optional[Dict[str, Any]]:
        """Parse an instruction email and extract processing details."""
        try:
            # Fetch the email
            status, msg_data = self.imap_server.fetch(email_id, '(RFC822)')
            
            if status != 'OK':
                logger.error(f"Failed to fetch email {email_id}")
                return None
            
            # Parse the email content
            raw_email = msg_data[0][1]
            email_message = email.message_from_bytes(raw_email)
            
            # Extract subject and body
            subject = email_message['Subject'] or ''
            from_addr = email_message['From'] or ''
            
            if not subject.startswith(self.SUBJECT_PREFIX):
                logger.warning(f"Email {email_id} doesn't have {self.SUBJECT_PREFIX} prefix")
                return None
            
            # Get email body (plain text or HTML)
            body = ""
            if email_message.is_multipart():
                for part in email_message.walk():
                    content_type = part.get_content_type()
                    if content_type == 'text/plain':
                        body = part.get_payload(decode=True).decode('utf-8', errors='replace')
                        break
                    elif content_type == 'text/html' and not body:
                        body = part.get_payload(decode=True).decode('utf-8', errors='replace')
            else:
                body = email_message.get_payload(decode=True).decode('utf-8', errors='replace')
            
            # Parse recipients from body
            recipients = self._parse_recipients(body)
            if not recipients:
                logger.warning(f"No recipients specified in email {email_id}")
                return None
            
            # Parse parameters from body
            params = self._parse_parameters(body)
            
            # Get attachments
            attachments = self._get_attachments(email_message)
            
            return {
                'email_id': email_id,
                'subject': subject,
                'from_addr': from_addr,
                'body': body,
                'recipients': recipients,
                'parameters': params,
                'attachments': attachments
            }
            
        except Exception as e:
            logger.error(f"Error parsing email {email_id}: {e}")
            return None
    
    def _parse_recipients(self, body: str) -> List[str]:
        """Parse recipient addresses from email body."""
        recipients = []
        
        # Look for recipients in various formats
        # Format: "Recipients: email1@example.com, email2@example.com"
        # Format: "To: email@example.com"
        # Format: "Send to: email@example.com"
        
        import re
        patterns = [
            r'(?:Recipients?|To|Send to):\s*([^\n]+)',
            r'RECIPIENTS:\s*([^\n]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, body, re.IGNORECASE)
            if match:
                recipients_str = match.group(1).strip()
                recipients = [r.strip() for r in recipients_str.split(',')]
                break
        
        # If no recipients found, use the sender as default
        if not recipients:
            logger.warning("No recipients found in body, will use sender")
        
        return recipients
    
    def _parse_parameters(self, body: str) -> Dict[str, str]:
        """Parse processing parameters from email body."""
        params = {}
        
        import re
        # Look for key: value pairs
        pattern = r'(\w+):\s*([^\n]+)'
        matches = re.finditer(pattern, body)
        
        for match in matches:
            key = match.group(1).strip().lower()
            value = match.group(2).strip()
            
            # Skip common email headers
            if key in ['subject', 'from', 'to', 'cc', 'bcc', 'date', 'recipients']:
                continue
            
            params[key] = value
        
        return params
    
    def _get_attachments(self, email_message: email.message.Message) -> List[Dict[str, Any]]:
        """Extract attachments from email."""
        attachments = []
        
        if email_message.is_multipart():
            for part in email_message.walk():
                if part.get_content_maintype() == 'multipart':
                    continue
                if part.get('Content-Disposition') is None:
                    continue
                
                filename = part.get_filename()
                if filename:
                    file_data = part.get_payload(decode=True)
                    attachments.append({
                        'filename': filename,
                        'data': file_data,
                        'size': len(file_data)
                    })
        
        return attachments
    
    def save_attachments(self, attachments: List[Dict[str, Any]], base_dir: str = None) -> List[str]:
        """Save attachments to temporary directory."""
        saved_paths = []
        
        if base_dir is None:
            base_dir = self.config.get('temp_dir', tempfile.gettempdir())
        
        os.makedirs(base_dir, exist_ok=True)
        
        for i, attachment in enumerate(attachments):
            filename = attachment['filename']
            
            # Sanitize filename
            import re
            safe_filename = re.sub(r'[^\w\-.]', '_', filename)
            
            filepath = os.path.join(base_dir, safe_filename)
            
            # Handle duplicate filenames
            counter = 1
            while os.path.exists(filepath):
                name, ext = os.path.splitext(safe_filename)
                filepath = os.path.join(base_dir, f"{name}_{counter}{ext}")
                counter += 1
            
            with open(filepath, 'wb') as f:
                f.write(attachment['data'])
            
            saved_paths.append(filepath)
            logger.info(f"Saved attachment: {filepath}")
        
        return saved_paths
    
    def execute_code(self, saved_paths: List[str], parameters: Dict[str, str]) -> Dict[str, Any]:
        """Execute the processing code with saved attachments."""
        result = {
            'success': False,
            'output': '',
            'error': '',
            'output_files': []
        }
        
        if not saved_paths:
            result['error'] = "No processing code attached"
            return result
        
        # Find the main processing script (look for .py files first)
        script_path = None
        for path in saved_paths:
            if path.endswith('.py'):
                script_path = path
                break
        
        if not script_path:
            script_path = saved_paths[0]  # Use first attachment if no .py found
            logger.warning(f"No .py file found, using first attachment: {script_path}")
        
        try:
            # Set up environment
            env = os.environ.copy()
            env['DATA_DIR'] = self.config['data_dir']
            
            # Add parameters as environment variables
            for key, value in parameters.items():
                env[f'PARAM_{key.upper()}'] = value
            
            # Build command
            cmd = [sys.executable, script_path]
            
            # Add data directory as argument
            cmd.append(self.config['data_dir'])
            
            # Add additional parameters as arguments
            for key, value in parameters.items():
                cmd.extend([f'--{key}', value])
            
            logger.info(f"Executing: {' '.join(cmd)}")
            
            # Execute the script
            import subprocess
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                cwd=os.path.dirname(script_path)
            )
            
            stdout, stderr = process.communicate(timeout=300)  # 5 minute timeout
            
            result['output'] = stdout.decode('utf-8', errors='replace')
            result['error'] = stderr.decode('utf-8', errors='replace')
            result['success'] = process.returncode == 0
            
            if result['success']:
                logger.info(f"Code executed successfully")
            else:
                logger.error(f"Code execution failed with return code {process.returncode}")
            
            # Find output files (look for common extensions)
            output_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.csv', '.txt', '.pdf', '.xlsx']
            output_dir = os.path.dirname(script_path)
            
            for filename in os.listdir(output_dir):
                if any(filename.endswith(ext) for ext in output_extensions):
                    filepath = os.path.join(output_dir, filename)
                    if os.path.isfile(filepath):
                        result['output_files'].append(filepath)
            
            logger.info(f"Found {len(result['output_files'])} output files")
            
        except subprocess.TimeoutExpired:
            result['error'] = "Code execution timed out (5 minutes)"
            logger.error("Code execution timed out")
        except Exception as e:
            result['error'] = f"Code execution error: {str(e)}"
            logger.error(f"Code execution error: {e}")
        
        return result
    
    def send_results(self, recipients: List[str], subject: str, 
                    result: Dict[str, Any], original_email_id: str = None) -> bool:
        """Send results back to specified recipients."""
        
        if not recipients:
            logger.error("No recipients to send results to")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.config['username']
            msg['To'] = ', '.join(recipients)
            msg['Subject'] = f"Re: {subject}" if subject else "Processing Results"
            
            # Build email body
            body = f"Processing results for: {subject}\n\n"
            
            if result['success']:
                body += "✅ Processing completed successfully\n\n"
            else:
                body += "❌ Processing failed\n\n"
            
            if result['output']:
                body += f"Output:\n{result['output']}\n\n"
            
            if result['error']:
                body += f"Error:\n{result['error']}\n\n"
            
            body += f"Processed at: {datetime.now().isoformat()}"
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Attach output files
            total_size = 0
            attached_files = []
            
            for filepath in result['output_files']:
                filesize = os.path.getsize(filepath)
                total_size += filesize
                
                # Check if adding this file would exceed limit
                if total_size > self.MAX_ATTACHMENT_SIZE:
                    logger.warning(f"Skipping {filepath} - would exceed attachment limit")
                    continue
                
                with open(filepath, 'rb') as f:
                    part = MIMEApplication(f.read(), Name=os.path.basename(filepath))
                part['Content-Disposition'] = f'attachment; filename="{os.path.basename(filepath)}"'
                msg.attach(part)
                attached_files.append(filepath)
                logger.info(f"Attached: {filepath} ({filesize} bytes)")
            
            if len(attached_files) < len(result['output_files']):
                body += f"\n⚠️  Some files were too large to attach (>25MB total)\n"
            
            # Send email
            self.connect_smtp()
            self.smtp_server.sendmail(
                self.config['username'],
                recipients,
                msg.as_string()
            )
            self.disconnect_smtp()
            
            logger.info(f"Results sent to: {', '.join(recipients)}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send results: {e}")
            return False
    
    def mark_as_processed(self, email_id: str, success: bool = True):
        """Mark an email as processed."""
        try:
            # Add appropriate label
            label = self.PROCESSED_LABEL if success else self.ERROR_LABEL
            
            # Copy to processed folder or add label
            self.imap_server.store(email_id, '+FLAGS', r'\Seen')
            self.imap_server.copy(email_id, f'"[{label}]"')
            self.imap_server.store(email_id, '+FLAGS', r'\Deleted')
            self.imap_server.expunge()
            
            logger.info(f"Marked email {email_id} as {label}")
            
        except Exception as e:
            logger.error(f"Failed to mark email {email_id} as processed: {e}")
    
    def process_email(self, email_id: str) -> bool:
        """Process a single instruction email."""
        logger.info(f"Processing email {email_id}")
        
        try:
            # Parse the email
            email_data = self.parse_email(email_id)
            if not email_data:
                logger.error(f"Failed to parse email {email_id}")
                self.mark_as_processed(email_id, success=False)
                return False
            
            logger.info(f"Parsed email: {email_data['subject']}")
            logger.info(f"Recipients: {email_data['recipients']}")
            logger.info(f"Parameters: {email_data['parameters']}")
            logger.info(f"Attachments: {[a['filename'] for a in email_data['attachments']]}")
            
            # Save attachments
            saved_paths = self.save_attachments(
                email_data['attachments'],
                base_dir=self.config.get('temp_dir', tempfile.gettempdir())
            )
            
            if not saved_paths:
                logger.error(f"No attachments found in email {email_id}")
                self.send_results(
                    email_data['recipients'],
                    email_data['subject'],
                    {'success': False, 'error': 'No processing code attached'},
                    email_id
                )
                self.mark_as_processed(email_id, success=False)
                return False
            
            # Execute the code
            result = self.execute_code(saved_paths, email_data['parameters'])
            
            # Send results
            success = self.send_results(
                email_data['recipients'],
                email_data['subject'],
                result,
                email_id
            )
            
            # Mark as processed
            self.mark_as_processed(email_id, success=result['success'])
            
            return result['success']
            
        except Exception as e:
            logger.error(f"Error processing email {email_id}: {e}")
            logger.error(traceback.format_exc())
            
            # Try to send error notification
            try:
                error_result = {
                    'success': False,
                    'error': f"Processing error: {str(e)}\n\n{traceback.format_exc()}",
                    'output': '',
                    'output_files': []
                }
                self.send_results(
                    email_data.get('recipients', []),
                    email_data.get('subject', 'Error'),
                    error_result,
                    email_id
                )
            except:
                pass
            
            self.mark_as_processed(email_id, success=False)
            return False
    
    def run(self, once: bool = False):
        """Main processing loop."""
        logger.info("Starting email processor")
        
        try:
            self.connect_imap()
            self._ensure_labels()
            
            while True:
                try:
                    # Find and process instruction emails
                    email_ids = self.find_instruction_emails()
                    
                    for email_id in email_ids:
                        email_id_str = email_id.decode('utf-8')
                        self.process_email(email_id_str)
                    
                    if once:
                        logger.info("Running once, exiting")
                        break
                    
                    # Wait before next poll
                    logger.info(f"Waiting {self.POLL_INTERVAL} seconds before next poll...")
                    time.sleep(self.POLL_INTERVAL)
                    
                except KeyboardInterrupt:
                    logger.info("Received interrupt signal, exiting")
                    break
                except Exception as e:
                    logger.error(f"Error in main loop: {e}")
                    time.sleep(10)  # Wait before retrying
            
        except Exception as e:
            logger.error(f"Fatal error: {e}")
            raise
        finally:
            self.disconnect_imap()
            self.disconnect_smtp()
            logger.info("Processor stopped")


def main():
    parser = argparse.ArgumentParser(description='Email-triggered data processor')
    parser.add_argument('--config', default='config/gmail_config.json', 
                        help='Path to config file')
    parser.add_argument('--once', action='store_true',
                        help='Run once and exit')
    parser.add_argument('--verbose', action='store_true',
                        help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Ensure directories exist
    os.makedirs('config', exist_ok=True)
    os.makedirs('logs', exist_ok=True)
    os.makedirs('scripts', exist_ok=True)
    os.makedirs('templates', exist_ok=True)
    
    processor = GmailProcessor(config_path=args.config)
    processor.run(once=args.once)


if __name__ == '__main__':
    main()
