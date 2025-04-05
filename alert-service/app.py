from kafka import KafkaConsumer
import json
import time
import os
import logging
import threading
from datetime import datetime
from flask import Flask, jsonify

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app for health check endpoint
app = Flask(__name__)

# Global variables
consumer = None

def init():
    global consumer
    
    # Get configuration from environment variables or use defaults
    kafka_host = os.environ.get('KAFKA_HOST', 'kafka:9092')
    
    # Initialize Kafka consumer for receiving fraud alerts
    retry_count = 0
    max_retries = 5
    while retry_count < max_retries:
        try:
            logger.info(f"Connecting to Kafka consumer at {kafka_host}")
            consumer = KafkaConsumer(
                'fraud-alerts',
                bootstrap_servers=kafka_host,
                group_id='fraud-alert-group',
                auto_offset_reset='earliest',
                value_deserializer=lambda v: json.loads(v.decode('utf-8')),
                key_deserializer=lambda k: k.decode('utf-8') if k else None
            )
            logger.info("Successfully connected to Kafka consumer")
            break
        except Exception as e:
            logger.error(f"Failed to connect to Kafka consumer: {str(e)}")
            retry_count += 1
            time.sleep(5)
    
    if retry_count >= max_retries:
        logger.error("Maximum retries reached. Could not connect to Kafka consumer.")
        raise Exception("Failed to connect to Kafka consumer after multiple attempts")


def process_alert(alert_message):
    """
    Process a fraud alert message and take appropriate action
    In a real-world scenario, this would send emails, SMS, or trigger other notification systems
    """
    try:
        alert_type = alert_message['alertType']
        transaction = alert_message['transaction']
        user_id = transaction['userId']
        amount = transaction['amount']
        currency = transaction['currency']
        location = transaction['location']
        transaction_id = transaction['transactionId']
        timestamp = datetime.fromtimestamp(transaction['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
        
        # Format the alert message
        alert_text = f"FRAUD ALERT: {alert_type}\n"
        alert_text += f"User ID: {user_id}\n"
        alert_text += f"Transaction ID: {transaction_id}\n"
        alert_text += f"Amount: {amount} {currency}\n"
        alert_text += f"Location: {location}\n"
        alert_text += f"Timestamp: {timestamp}\n"
        
        # Add details based on alert type
        if alert_type == 'large_transaction_detected':
            threshold = alert_message['details']['threshold']
            alert_text += f"Threshold exceeded: {threshold} {currency}\n"
        
        elif alert_type == 'multiple_rapid_transactions_detected':
            count = alert_message['details']['count']
            time_window = alert_message['details']['time_window']
            alert_text += f"Multiple transactions detected: {count} transactions in {time_window:.2f} seconds\n"
        
        elif alert_type == 'unusual_location_change_detected':
            previous_location = alert_message['details']['previous_location']
            current_location = alert_message['details']['current_location']
            alert_text += f"Location change detected: {previous_location} -> {current_location}\n"
        
        # In a real-world scenario, this would send the alert through appropriate channels
        # For demonstration purposes, just log the alert
        logger.info(f"\n{'='*60}\n{alert_text}{'='*60}")
        
        # Here you would add code to send email, SMS, or other notifications
        # For example:
        # send_email(user.email, "Fraud Alert", alert_text)
        # send_sms(user.phone, alert_text)
        
    except Exception as e:
        logger.error(f"Error processing alert: {str(e)}")


@app.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint
    """
    try:
        # Check if consumer is connected
        if consumer is None:
            return jsonify({
                'status': 'unhealthy',
                'consumer': False
            }), 500
        
        # Check Kafka consumer connection
        consumer.topics()
        
        return jsonify({
            'status': 'healthy',
            'consumer': True
        }), 200
    
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500


def main_loop():
    """
    Main loop to consume fraud alerts from Kafka and process them
    """
    logger.info("Starting alert service...")
    
    try:
        for message in consumer:
            try:
                alert_message = message.value
                logger.info(f"Received fraud alert: {alert_message['alertType']}")
                process_alert(alert_message)
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}")
    except Exception as e:
        logger.error(f"Error in main loop: {str(e)}")
        time.sleep(5)  # Wait before retrying


if __name__ == '__main__':
    init()
    # Run Flask in a separate thread
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)).start()
    # Run the main Kafka consumer loop
    main_loop() 