# Email-Triggered Local Data Processing for Electrochemical Data

This system allows users to trigger data processing on a lab computer by sending an email with processing instructions and code attachments.

## Overview

1. **User sends email** with `[RUN]` in subject line, recipient addresses, parameters, and attached processing code
2. **Lab computer script** polls Gmail inbox every 1-5 minutes
3. **Script processes** the email: saves attachments, runs the code with local data paths
4. **Results are emailed** back to specified recipients with graphs and CSVs attached
5. **Original email** is marked as processed to prevent duplicate execution

## Setup

### Prerequisites

- Python 3.7+
- Gmail account with IMAP and SMTP access enabled
- App password or OAuth credentials for the Gmail account
- Local electrochemical data accessible to the processing script

### Installation

```bash
# Clone or copy this repository
cd email_triggered_processing

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

1. Copy the template config file:
```bash
cp config/gmail_config_template.json config/gmail_config.json
```

2. Edit `config/gmail_config.json` with your Gmail credentials:
```json
{
    "imap_server": "imap.gmail.com",
    "imap_port": 993,
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "username": "your-lab-gmail-account@gmail.com",
    "password": "your-app-password",
    "data_dir": "/path/to/your/electrochemical/data",
    "temp_dir": "temp"
}
```

**Important:** Use an [App Password](https://myaccount.google.com/apppasswords) for the Gmail account, not the regular password.

### Gmail Setup

1. Enable IMAP access in the Gmail account:
   - Go to Gmail Settings > Forwarding and POP/IMAP > Enable IMAP
2. Create an App Password:
   - Go to Google Account > Security > App Passwords
   - Generate a password for "Mail" and select "Other" device
3. Ensure the Gmail account has enough storage for attachments

## Email Format

### Subject Line
Must start with `[RUN]` followed by a description:
```
[RUN] Process cyclic voltammetry data
[RUN] Analyze impedance spectroscopy
```

### Email Body
Specify recipients and parameters:
```
Recipients: user1@example.com, user2@example.com

data_file: CV_2024_01_01.csv
analysis_type: peak_detection
output_prefix: my_experiment

Additional parameters:
threshold: 0.5
smoothing: true
```

### Attachments
- Processing script (Python file with .py extension)
- Optional: Additional data files or configuration

## Running the Processor

### Manual Run
```bash
# Run once and exit
python processor.py --once

# Run with custom config
python processor.py --config config/my_config.json

# Run with verbose logging
python processor.py --verbose
```

### Scheduled Run (Linux/macOS with cron)

Edit crontab:
```bash
crontab -e
```

Add line to run every 2 minutes:
```
*/2 * * * * /path/to/venv/bin/python /path/to/processor.py --config /path/to/config/gmail_config.json >> /path/to/logs/processor.log 2>&1
```

### Scheduled Run (Windows with Task Scheduler)

1. Create a new task
2. Set trigger to "Repeat task every" 2 minutes
3. Set action to start program: `python.exe`
4. Add arguments: `processor.py --config config/gmail_config.json`
5. Set working directory to the project folder

## Creating Processing Scripts

See `templates/example_processing_script.py` for a complete example.

### Script Requirements
- Accept command-line arguments for data directory and parameters
- Save output files (graphs, CSVs) to accessible locations
- Handle errors gracefully with informative messages

### Available Environment Variables
The processor sets these environment variables:
- `DATA_DIR`: Path to the data directory
- `PARAM_*`: All parameters from the email (uppercase with PARAM_ prefix)

## Security Considerations

**⚠️ Security is deferred for prototyping. For production:**
- Use a dedicated Gmail account with limited permissions
- Implement code signing/verification for attached scripts
- Add sender authentication to only accept emails from authorized users
- Consider using a whitelist of allowed senders
- Implement rate limiting to prevent abuse
- Use a separate service account with limited access

## Error Handling

- If processing fails, the processor will email back a traceback
- Failed emails are marked with the "ERROR" label
- Successful emails are marked with the "PROCESSED" label
- Check `logs/processor.log` for detailed error information

## Output Size Limits

- Gmail has a 25MB attachment limit
- If total output exceeds 25MB, some files may be skipped
- Consider compressing large output files or providing download links

## Troubleshooting

### Common Issues

1. **IMAP connection fails**: Verify app password and IMAP is enabled
2. **SMTP connection fails**: Check SMTP server settings and authentication
3. **No emails found**: Verify subject line starts with `[RUN]` and emails are unread
4. **Code execution fails**: Check the processing script for errors and dependencies

### Debug Mode

Run with verbose logging:
```bash
python processor.py --verbose
```

### Test Email

Send a test email with:
- Subject: `[RUN] Test processing`
- Body: `Recipients: your-email@example.com`
- Attachment: `templates/example_processing_script.py`

## Project Structure

```
email_triggered_processing/
├── processor.py           # Main processing script
├── requirements.txt       # Python dependencies
├── README.md              # This documentation
├── config/
│   └── gmail_config_template.json
├── templates/
│   └── example_processing_script.py
├── scripts/               # Additional utility scripts
└── logs/                  # Log files
```

## License

MIT License - Feel free to use and modify for your lab's needs.
