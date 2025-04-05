from flask import Flask, request, jsonify
from kafka import KafkaProducer
import redis
import uuid
import json
import time
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

producer = None
redis_client = None

def init():
    global producer, redis_client
    
    # Get configuration from environment variables or use defaults
    kafka_host = os.environ.get('KAFKA_HOST', 'kafka:9092')
    redis_host = os.environ.get('REDIS_HOST', 'redis')
    redis_port = int(os.environ.get('REDIS_PORT', 6379))
    redis_password = os.environ.get('REDIS_PASSWORD', 'scan_remember')
    
    # Initialize Kafka producer
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
            logger.info("Successfully connected to Kafka")
            break
        except Exception as e:
            logger.error(f"Failed to connect to Kafka: {str(e)}")
            retry_count += 1
            time.sleep(5)
    
    if retry_count >= max_retries:
        logger.error("Maximum retries reached. Could not connect to Kafka.")
        raise Exception("Failed to connect to Kafka after multiple attempts")
    
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


@app.route('/api/v1/transactions', methods=['POST'])
def process_transaction():
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        # Validate required fields
        required_fields = ['userId', 'amount', 'currency', 'location']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        user_id = data['userId']
        amount = float(data['amount'])
        currency = data['currency']
        location = data['location']
        transaction_id = str(uuid.uuid4())
        
        # Create transaction record
        transaction_record = {
            'transactionId': transaction_id,
            'userId': user_id,
            'amount': amount,
            'currency': currency,
            'location': location,
            'timestamp': time.time()
        }
        
        # Store transaction in Redis
        transaction_json = json.dumps(transaction_record)
        redis_client.rpush(f'user:{user_id}:transactions', transaction_json)
        redis_client.ltrim(f'user:{user_id}:transactions', 0, 9)  # Keep only the last 10 transactions
        
        # Store timestamp for rapid transaction detection
        redis_client.rpush(f'user:{user_id}:transaction_timestamps', transaction_record['timestamp'])
        redis_client.ltrim(f'user:{user_id}:transaction_timestamps', 0, 4)  # Keep only the last 5 timestamps
        
        # Send transaction to Kafka
        logger.info(f"Sending transaction {transaction_id} to Kafka topic 'transactions'")
        producer.send('transactions', key=user_id, value=transaction_record)
        
        return jsonify({
            'status': 'success',
            'transactionId': transaction_id
        }), 201
    
    except Exception as e:
        logger.error(f"Error processing transaction: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/v1/health', methods=['GET'])
def health_check():
    try:
        # Check Redis connection
        redis_client.ping()
        
        # Check Kafka connection (a simple metadata request)
        producer.metrics()
        
        return jsonify({
            'status': 'healthy',
            'redis': 'connected',
            'kafka': 'connected'
        }), 200
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500


if __name__ == '__main__':
    init()
    app.run(host='0.0.0.0', port=3000, debug=False) 