# Real-Time Fraud Detection System - Testing Guide

This document outlines the testing procedures for the Kafka Real-Time Fraud Detection System. It includes various test scenarios to verify the system's functionality, integration, and fraud detection capabilities.

## Prerequisites

- The system is up and running via `docker-compose up -d`
- [Postman](https://www.postman.com/downloads/) or similar API testing tool
- Basic understanding of REST API concepts

## 1. Service Health Verification

Before testing functionality, verify all services are healthy:

### 1.1 Transaction Service

**Request:**
```
GET http://localhost:3001/api/v1/health
```

**Expected Response:** (Status Code: 200 OK)
```json
{
  "status": "healthy",
  "redis": "connected",
  "kafka": "connected"
}
```

### 1.2 Fraud Detection Service

**Request:**
```
GET http://localhost:5001/health
```

**Expected Response:** (Status Code: 200 OK)
```json
{
  "status": "healthy",
  "consumer": true,
  "producer": true,
  "redis": true
}
```

### 1.3 Alert Service

**Request:**
```
GET http://localhost:5002/health
```

**Expected Response:** (Status Code: 200 OK)
```json
{
  "status": "healthy",
  "consumer": true
}
```

## 2. Basic Transaction Processing

### 2.1 Submit a Valid Transaction

**Request:**
```
POST http://localhost:3001/api/v1/transactions
```

**Headers:**
```
Content-Type: application/json
```

**Body:**
```json
{
  "userId": "user1",
  "amount": 500.00,
  "currency": "USD",
  "location": "New York"
}
```

**Expected Response:** (Status Code: 201 Created)
```json
{
  "status": "success",
  "transactionId": "uuid-string"
}
```

### 2.2 Input Validation Test

**Request:**
```
POST http://localhost:3001/api/v1/transactions
```

**Headers:**
```
Content-Type: application/json
```

**Body:**
```json
{
  "userId": "user1",
  "currency": "USD",
  "location": "New York"
}
```

**Expected Response:** (Status Code: 400 Bad Request)
```json
{
  "error": "Missing required field: amount"
}
```

## 3. Fraud Detection Rule Testing

### 3.1 Large Transaction Amount (Rule 1)

**Test Scenario:** Submit a transaction with an amount exceeding the threshold ($10,000)

**Request:**
```
POST http://localhost:3001/api/v1/transactions
```

**Headers:**
```
Content-Type: application/json
```

**Body:**
```json
{
  "userId": "user1",
  "amount": 12000.00,
  "currency": "USD",
  "location": "New York"
}
```

**Expected Response:** (Status Code: 201 Created)
```json
{
  "status": "success",
  "transactionId": "uuid-string"
}
```

**Verification:**
1. Check the logs of the fraud-detection-service:
   ```bash
   docker-compose logs -f fraud-detection-service
   ```
   Look for: `Large transaction detected: 12000.0 USD`

2. Check the logs of the alert-service:
   ```bash
   docker-compose logs -f alert-service
   ```
   Look for: `FRAUD ALERT: large_transaction_detected`

3. Check Kafka UI (http://localhost:8081):
   - Verify a message was published to the "fraud-alerts" topic
   - Examine the message content to confirm it contains the correct alert type

### 3.2 Multiple Rapid Transactions (Rule 2)

**Test Scenario:** Submit 6 transactions for the same user within 30 seconds

**Request (repeated 6 times with minimal delay between requests):**
```
POST http://localhost:3001/api/v1/transactions
```

**Headers:**
```
Content-Type: application/json
```

**Body:**
```json
{
  "userId": "user2",
  "amount": 100.00,
  "currency": "USD",
  "location": "London"
}
```

**Expected Response:** (Status Code: 201 Created)
```json
{
  "status": "success",
  "transactionId": "uuid-string"
}
```

**Verification:**
1. Check the logs of the fraud-detection-service:
   ```bash
   docker-compose logs -f fraud-detection-service
   ```
   Look for: `Rapid transactions detected: x transactions in y.yy seconds`

2. Check the logs of the alert-service:
   ```bash
   docker-compose logs -f alert-service
   ```
   Look for: `FRAUD ALERT: multiple_rapid_transactions_detected`

3. Check Redis UI (http://localhost:8001):
   - Verify the transaction timestamps are being stored for the user
   - Confirm there are 5 timestamps stored (after 6 transactions)

### 3.3 Location Change Detection (Rule 3)

**Test Scenario:** Submit two transactions for the same user from significantly different locations

**Step 1 - First Transaction:**
```
POST http://localhost:3001/api/v1/transactions
```

**Headers:**
```
Content-Type: application/json
```

**Body:**
```json
{
  "userId": "user3",
  "amount": 200.00,
  "currency": "USD",
  "location": "Tokyo"
}
```

**Step 2 - Second Transaction (after 2-5 seconds):**
```
POST http://localhost:3001/api/v1/transactions
```

**Headers:**
```
Content-Type: application/json
```

**Body:**
```json
{
  "userId": "user3",
  "amount": 300.00,
  "currency": "USD",
  "location": "New York"
}
```

**Expected Response for both:** (Status Code: 201 Created)
```json
{
  "status": "success",
  "transactionId": "uuid-string"
}
```

**Verification:**
1. Check the logs of the fraud-detection-service:
   ```bash
   docker-compose logs -f fraud-detection-service
   ```
   Look for: `Unusual location change detected: Tokyo -> New York`

2. Check the logs of the alert-service:
   ```bash
   docker-compose logs -f alert-service
   ```
   Look for: `FRAUD ALERT: unusual_location_change_detected`

3. Check Redis UI (http://localhost:8001):
   - Verify the user location has been updated from "Tokyo" to "New York"

## 4. Advanced Testing

### 4.1 Load Testing

Use a script or tool like Apache JMeter to generate multiple concurrent transactions:

1. Generate a sequence of 100 transactions with random user IDs, amounts, and locations
2. Send transactions at a rate of at least 10 per second
3. Verify all transactions are processed correctly, and fraud detection rules are applied

### 4.2 Failure Recovery

1. Start the system and process a few transactions
2. Stop one of the services (e.g., `docker-compose stop fraud-detection-service`)
3. Continue sending transactions
4. Verify transactions are still accepted by the Transaction Service
5. Restart the stopped service (`docker-compose start fraud-detection-service`)
6. Verify the service recovers and continues processing from where it left off
7. Check that no fraud alerts were missed during the outage

### 4.3 Session Persistence

1. Submit a transaction for a new user
2. Stop and restart all services (`docker-compose down` followed by `docker-compose up -d`)
3. Submit a second transaction for the same user with a different location
4. Verify the location change is detected, indicating that Redis data persisted across restarts

## 5. Monitoring During Tests

### 5.1 Kafka UI (http://localhost:8081)

Monitor:
- Topic message counts
- Consumer group offsets
- Lag metrics
- Message content by sampling messages

### 5.2 Redis UI (http://localhost:8001)

Monitor:
- Key creation and updates
- List lengths for transaction history
- Memory usage
- Command statistics

### 5.3 Docker Container Logs

Continuously monitor logs for real-time insights:

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f transaction-service
docker-compose logs -f fraud-detection-service
docker-compose logs -f alert-service
```

## 6. Automated Testing with Python Client

The project includes a test client for automated testing:

```bash
# Check health of all services
python test-client.py --health

# Run specific test scenarios
python test-client.py --test large
python test-client.py --test rapid
python test-client.py --test location

# Run all tests with custom parameters
python test-client.py --count 20 --delay 0.5
```

## 7. Troubleshooting Failed Tests

### 7.1 Common Issues

1. **Services Not Healthy**
   - Check if containers are running: `docker-compose ps`
   - Inspect container logs for error messages
   - Verify network configuration in docker-compose.yml

2. **Transactions Not Being Processed**
   - Check if Kafka topics exist and are properly configured
   - Verify consumer groups are active and consuming messages
   - Check for connection errors in service logs

3. **Fraud Rules Not Triggering**
   - Verify threshold values in the fraud detection service
   - Check Redis data to ensure transaction history is being stored
   - Confirm Kafka messages contain the expected format and data

### 7.2 Resolving Issues

1. **Restart Specific Services**
   ```bash
   docker-compose restart <service-name>
   ```

2. **Reset the System**
   ```bash
   docker-compose down -v
   docker-compose up -d
   ```

3. **Manually Create Kafka Topics**
   ```bash
   chmod +x create-topics.sh
   ./create-topics.sh
   ```

## 8. Test Completion Checklist

- [ ] All health checks return 200 OK responses
- [ ] Basic transaction processing works correctly
- [ ] Large transaction detection (Rule 1) identifies transactions > $10,000
- [ ] Rapid transaction detection (Rule 2) identifies 5+ transactions within 30 seconds
- [ ] Location change detection (Rule 3) identifies suspicious location changes
- [ ] Data is properly stored in Redis and Kafka
- [ ] System recovers from service failures
- [ ] Alert service properly processes and logs fraud alerts