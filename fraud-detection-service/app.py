from kafka import KafkaConsumer, KafkaProducer
import redis
import json
import time
import os
import logging
import threading
from datetime import datetime
import math
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
producer = None
redis_client = None

# Fraud detection thresholds
LARGE_TRANSACTION_THRESHOLD = 10000  # Amount in currency units
RAPID_TRANSACTIONS_TIME_WINDOW = 30  # Time window in seconds
RAPID_TRANSACTIONS_COUNT = 5  # Number of transactions to be considered rapid

def init():
    global consumer, producer, redis_client
    
    # Get configuration from environment variables or use defaults
    kafka_host = os.environ.get('KAFKA_HOST', 'kafka:9092')
    redis_host = os.environ.get('REDIS_HOST', 'redis')
    redis_port = int(os.environ.get('REDIS_PORT', 6379))
    redis_password = os.environ.get('REDIS_PASSWORD', 'scan_remember')
    
    # Initialize Kafka producer for sending fraud alerts
    retry_count = 0
    max_retries = 5
    while retry_count < max_retries:
        try:
            logger.info(f"Connecting to Kafka broker at {kafka_host}")
            producer = KafkaProducer(
                bootstrap_servers=kafka_host,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if isinstance(k, str) else str(k).encode('utf-8')
            )
            logger.info("Successfully connected to Kafka producer")
            break
        except Exception as e:
            logger.error(f"Failed to connect to Kafka producer: {str(e)}")
            retry_count += 1
            time.sleep(5)
    
    if retry_count >= max_retries:
        logger.error("Maximum retries reached. Could not connect to Kafka producer.")
        raise Exception("Failed to connect to Kafka producer after multiple attempts")
    
    # Initialize Kafka consumer for receiving transactions
    retry_count = 0
    while retry_count < max_retries:
        try:
            logger.info(f"Connecting to Kafka consumer at {kafka_host}")
            consumer = KafkaConsumer(
                'transactions',
                bootstrap_servers=kafka_host,
                group_id='fraud-detection-group',
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
    
    # Initialize Redis client
    retry_count = 0
    while retry_count < max_retries:
        try:
            logger.info(f"Connecting to Redis at {redis_host}:{redis_port}")
            redis_client = redis.Redis(
                host=redis_host,
                port=redis_port,
                password=redis_password,
                decode_responses=True
            )
            redis_client.ping()  # Test connection
            logger.info("Successfully connected to Redis")
            break
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            retry_count += 1
            time.sleep(5)
    
    if retry_count >= max_retries:
        logger.error("Maximum retries reached. Could not connect to Redis.")
        raise Exception("Failed to connect to Redis after multiple attempts")


def send_fraud_alert(alert_type, transaction_record, details=None):
    """
    Send a fraud alert message to the fraud-alerts Kafka topic
    """
    try:
        user_id = transaction_record['userId']
        alert_message = {
            'alertType': alert_type,
            'transaction': transaction_record,
            'timestamp': time.time(),
            'details': details or {}
        }
        
        logger.info(f"Sending fraud alert for user {user_id}: {alert_type}")
        producer.send('fraud-alerts', key=user_id, value=alert_message)
    except Exception as e:
        logger.error(f"Error sending fraud alert: {str(e)}")


def detect_large_transaction(transaction_record):
    """
    Rule 1: Detect transactions with amount exceeding the threshold
    """
    try:
        amount = transaction_record['amount']
        if amount > LARGE_TRANSACTION_THRESHOLD:
            logger.info(f"Large transaction detected: {amount} {transaction_record['currency']}")
            send_fraud_alert(
                'large_transaction_detected', 
                transaction_record,
                {'threshold': LARGE_TRANSACTION_THRESHOLD}
            )
            return True
        return False
    except Exception as e:
        logger.error(f"Error in large transaction detection: {str(e)}")
        return False


def detect_rapid_transactions(transaction_record):
    """
    Rule 2: Detect multiple transactions from the same account in a short time frame
    """
    try:
        user_id = transaction_record['userId']
        timestamp_key = f'user:{user_id}:transaction_timestamps'
        
        # Get the last 5 transaction timestamps from Redis
        timestamps = redis_client.lrange(timestamp_key, 0, -1)
        
        if len(timestamps) >= RAPID_TRANSACTIONS_COUNT:
            # Convert timestamp strings to float
            timestamps = [float(ts) for ts in timestamps]
            
            # Sort timestamps in ascending order
            timestamps.sort()
            
            # Calculate time difference between oldest and newest timestamp
            first_timestamp = timestamps[0]
            last_timestamp = timestamps[-1]
            time_difference = last_timestamp - first_timestamp
            
            if time_difference < RAPID_TRANSACTIONS_TIME_WINDOW:
                logger.info(f"Rapid transactions detected: {len(timestamps)} transactions in {time_difference:.2f} seconds")
                send_fraud_alert(
                    'multiple_rapid_transactions_detected', 
                    transaction_record,
                    {
                        'count': len(timestamps),
                        'time_window': time_difference,
                        'threshold_count': RAPID_TRANSACTIONS_COUNT,
                        'threshold_time': RAPID_TRANSACTIONS_TIME_WINDOW
                    }
                )
                return True
        return False
    except Exception as e:
        logger.error(f"Error in rapid transactions detection: {str(e)}")
        return False


def detect_unusual_location_change(transaction_record):
    """
    Rule 3: Detect transactions originating from significantly different locations in a short period
    """
    try:
        user_id = transaction_record['userId']
        current_location = transaction_record['location']
        location_key = f'user:{user_id}:location'
        
        # Get the last known location from Redis
        last_location = redis_client.get(location_key)
        
        if last_location and last_location != current_location:
            logger.info(f"Unusual location change detected: {last_location} -> {current_location}")
            send_fraud_alert(
                'unusual_location_change_detected', 
                transaction_record,
                {
                    'previous_location': last_location,
                    'current_location': current_location
                }
            )
            # Update the location in Redis
            redis_client.set(location_key, current_location)
            return True
        else:
            # If no previous location or same location, just update it
            redis_client.set(location_key, current_location)
            return False
    except Exception as e:
        logger.error(f"Error in unusual location change detection: {str(e)}")
        return False


def process_transaction(transaction_record):
    """
    Process a transaction and apply fraud detection rules
    """
    try:
        logger.info(f"Processing transaction: {transaction_record['transactionId']}")
        
        # Apply fraud detection rules
        large_transaction = detect_large_transaction(transaction_record)
        rapid_transactions = detect_rapid_transactions(transaction_record)
        unusual_location = detect_unusual_location_change(transaction_record)
        
        # Log the results
        if large_transaction or rapid_transactions or unusual_location:
            logger.info(f"Fraud detected in transaction {transaction_record['transactionId']}")
        else:
            logger.info(f"No fraud detected in transaction {transaction_record['transactionId']}")
    
    except Exception as e:
        logger.error(f"Error processing transaction: {str(e)}")


@app.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint
    """
    try:
        # Check if consumer and producer are connected
        if consumer is None or producer is None or redis_client is None:
            return jsonify({
                'status': 'unhealthy',
                'consumer': consumer is not None,
                'producer': producer is not None,
                'redis': redis_client is not None
            }), 500
        
        # Check Kafka producer connection
        producer.metrics()
        
        # Check Redis connection
        redis_client.ping()
        
        return jsonify({
            'status': 'healthy',
            'consumer': True,
            'producer': True,
            'redis': True
        }), 200
    
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500


def main_loop():
    """
    Main loop to consume transactions from Kafka and process them
    """
    logger.info("Starting fraud detection service...")
    
    try:
        for message in consumer:
            try:
                transaction_record = message.value
                process_transaction(transaction_record)
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