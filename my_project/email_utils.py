# email_utils.py
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app

def send_email(subject, body, recipients):
    sender_email = current_app.config['MAIL_USERNAME']
    
    # Create the email header
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = ", ".join(recipients)  # Join all recipients into a single string
    msg['Subject'] = subject
    
    # Attach the email body
    msg.attach(MIMEText(body, 'plain'))

    try:
        # Connect to the SMTP server
        with smtplib.SMTP(current_app.config['MAIL_SERVER'], current_app.config['MAIL_PORT']) as server:
            server.starttls()
            server.login(sender_email, current_app.config['MAIL_PASSWORD'])
            server.sendmail(sender_email, recipients, msg.as_string())
            current_app.logger.info("Email sent successfully")
    except Exception as e:
        current_app.logger.error(f"Failed to send email: {e}")
