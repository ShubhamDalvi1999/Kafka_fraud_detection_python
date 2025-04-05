import requests
import json
import time
import random
import uuid
import argparse

# Service URLs
TRANSACTION_SERVICE_URL = "http://localhost:3001/api/v1/transactions"
TRANSACTION_HEALTH_URL = "http://localhost:3001/api/v1/health"
FRAUD_DETECTION_HEALTH_URL = "http://localhost:5001/health"
ALERT_SERVICE_HEALTH_URL = "http://localhost:5002/health"

# Sample user IDs
USER_IDS = ["user1", "user2", "user3", "user4", "user5"]

# Sample locations
LOCATIONS = ["New York", "London", "Tokyo", "Sydney", "Mumbai", "Paris", "Berlin", "Toronto", "Singapore", "Dubai"]

def generate_transaction(user_id=None, amount=None, location=None):
    """
    Generate a random transaction or use provided parameters
    """
    if user_id is None:
        user_id = random.choice(USER_IDS)
    
    if amount is None:
        # Generate random amount between $10 and $15,000
        amount = round(random.uniform(10, 15000), 2)
    
    if location is None:
        location = random.choice(LOCATIONS)
    
    return {
        "userId": user_id,
        "amount": amount,
        "currency": "USD",
        "location": location
    }

def send_transaction(transaction):
    """
    Send a transaction to the Transaction Service
    """
    try:
        response = requests.post(
            TRANSACTION_SERVICE_URL,
            json=transaction,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 201:
            result = response.json()
            print(f"Transaction sent successfully: {result['transactionId']}")
            print(f"  User ID: {transaction['userId']}")
            print(f"  Amount: ${transaction['amount']} {transaction['currency']}")
            print(f"  Location: {transaction['location']}")
            return True
        else:
            print(f"Failed to send transaction: {response.status_code} - {response.text}")
            return False
    
    except Exception as e:
        print(f"Error sending transaction: {str(e)}")
        return False

def check_service_health():
    """
    Check the health of all services
    """
    services_healthy = True
    
    # Check Transaction Service
    try:
        print("Checking Transaction Service health...")
        response = requests.get(TRANSACTION_HEALTH_URL)
        if response.status_code == 200:
            print("  Transaction Service: HEALTHY")
        else:
            print(f"  Transaction Service: UNHEALTHY - {response.status_code} - {response.text}")
            services_healthy = False
    except Exception as e:
        print(f"  Transaction Service: UNHEALTHY - {str(e)}")
        services_healthy = False
    
    # Check Fraud Detection Service
    try:
        print("Checking Fraud Detection Service health...")
        response = requests.get(FRAUD_DETECTION_HEALTH_URL)
        if response.status_code == 200:
            print("  Fraud Detection Service: HEALTHY")
        else:
            print(f"  Fraud Detection Service: UNHEALTHY - {response.status_code} - {response.text}")
            services_healthy = False
    except Exception as e:
        print(f"  Fraud Detection Service: UNHEALTHY - {str(e)}")
        services_healthy = False
    
    # Check Alert Service
    try:
        print("Checking Alert Service health...")
        response = requests.get(ALERT_SERVICE_HEALTH_URL)
        if response.status_code == 200:
            print("  Alert Service: HEALTHY")
        else:
            print(f"  Alert Service: UNHEALTHY - {response.status_code} - {response.text}")
            services_healthy = False
    except Exception as e:
        print(f"  Alert Service: UNHEALTHY - {str(e)}")
        services_healthy = False
    
    return services_healthy

def test_large_transaction():
    """
    Test the large transaction fraud detection rule
    """
    print("\n=== Testing Large Transaction Detection ===")
    # Generate a transaction with amount exceeding the threshold ($10,000)
    transaction = generate_transaction(amount=12000)
    send_transaction(transaction)

def test_rapid_transactions():
    """
    Test the rapid transactions fraud detection rule
    """
    print("\n=== Testing Rapid Transactions Detection ===")
    user_id = random.choice(USER_IDS)
    location = random.choice(LOCATIONS)
    
    print(f"Sending 6 transactions for user {user_id} in rapid succession...")
    
    for i in range(6):
        transaction = generate_transaction(
            user_id=user_id,
            amount=random.uniform(100, 500),
            location=location
        )
        send_transaction(transaction)
        # Small delay to simulate rapid but not instantaneous transactions
        time.sleep(0.5)

def test_location_change():
    """
    Test the unusual location change fraud detection rule
    """
    print("\n=== Testing Unusual Location Change Detection ===")
    user_id = random.choice(USER_IDS)
    
    # First transaction from one location
    first_location = "New York"
    print(f"Sending transaction for user {user_id} from {first_location}")
    transaction1 = generate_transaction(
        user_id=user_id,
        amount=random.uniform(100, 500),
        location=first_location
    )
    send_transaction(transaction1)
    
    # Short delay
    time.sleep(2)
    
    # Second transaction from a different location
    second_location = "Tokyo"
    print(f"Sending transaction for user {user_id} from {second_location}")
    transaction2 = generate_transaction(
        user_id=user_id,
        amount=random.uniform(100, 500),
        location=second_location
    )
    send_transaction(transaction2)

def random_transactions(count, delay=1):
    """
    Send a specified number of random transactions
    """
    print(f"\n=== Sending {count} Random Transactions ===")
    for i in range(count):
        transaction = generate_transaction()
        success = send_transaction(transaction)
        if not success:
            print("Stopping due to error")
            break
        time.sleep(delay)

def main():
    parser = argparse.ArgumentParser(description='Test client for Fraud Detection System')
    parser.add_argument('--test', choices=['large', 'rapid', 'location', 'random', 'all'], 
                        default='all', help='Test to run')
    parser.add_argument('--count', type=int, default=10, 
                        help='Number of random transactions to send')
    parser.add_argument('--delay', type=float, default=1.0, 
                        help='Delay between random transactions in seconds')
    parser.add_argument('--health', action='store_true',
                        help='Check health of all services before running tests')
    
    args = parser.parse_args()
    
    # Check health of all services
    if args.health or args.test != 'health':
        print("\n=== Checking Service Health ===")
        services_healthy = check_service_health()
        
        if not services_healthy:
            print("\nSome services are unhealthy. Please check the logs and service status.")
            if not args.health:  # Only exit if just checking health
                print("Run with --health flag only to check service health without running tests.")
                print("Continuing with tests anyway...")
    
    # If only checking health, exit now
    if args.health and args.test == 'all':
        return
    
    if args.test == 'large' or args.test == 'all':
        test_large_transaction()
    
    if args.test == 'rapid' or args.test == 'all':
        test_rapid_transactions()
    
    if args.test == 'location' or args.test == 'all':
        test_location_change()
    
    if args.test == 'random' or args.test == 'all':
        random_transactions(args.count, args.delay)

if __name__ == "__main__":
    main() 