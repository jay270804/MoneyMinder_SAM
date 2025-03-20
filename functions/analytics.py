import pytz  # Add this import at the top
import json
import boto3
import os
import decimal
from datetime import datetime
from collections import defaultdict
import logging

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            return float(o) if o % 1 != 0 else int(o)
        return super(DecimalEncoder, self).default(o)

dynamodb = boto3.resource('dynamodb')
transactions_table = dynamodb.Table(os.environ['TRANSACTIONS_TABLE'])
budgets_table = dynamodb.Table(os.environ['BUDGETS_TABLE'])

def analyze_spending(event, context):
    """Analyze spending patterns by category and time period"""
    logger.info("Starting analyze_spending with event: %s", json.dumps(event))

    try:
        user_id = event['requestContext']['authorizer']['claims']['sub']
        logger.info("Analyzing spending for user: %s", user_id)

        params = event.get('queryStringParameters', {}) or {}
        logger.debug("Query parameters: %s", json.dumps(params))

        # Update date handling to use IST
        ist_timezone = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist_timezone)

        # Default to current month if no date range specified
        start_date = params.get('startDate', now.strftime('%Y-%m-01'))
        end_date = params.get('endDate', now.strftime('%Y-%m-%d'))
        logger.info("Analyzing period from %s to %s (IST)", start_date, end_date)

        # Query transactions
        response = transactions_table.query(
            KeyConditionExpression='userId = :uid',
            FilterExpression='#dt BETWEEN :start AND :end',
            ExpressionAttributeNames={'#dt': 'date'},
            ExpressionAttributeValues={
                ':uid': user_id,
                ':start': start_date,
                ':end': end_date
            }
        )

        transaction_count = len(response.get('Items', []))
        logger.info("Retrieved %d transactions for analysis", transaction_count)

        # Categorize spending
        spending = defaultdict(float)
        for item in response.get('Items', []):
            spending[item['category']] += float(item['amount'])

        total_spent = sum(spending.values())
        logger.info("Total spending: %s, Categories analyzed: %d",
                   total_spent, len(spending))
        logger.debug("Spending by category: %s", json.dumps(dict(spending)))

        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'startDate': start_date,
                'endDate': end_date,
                'spendingByCategory': dict(spending),
                'totalSpent': total_spent
            }, cls=DecimalEncoder)
        }
    except Exception as e:
        logger.error("Error analyzing spending: %s", str(e), exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def budget_status(event, context):
    """Check current status of all budgets"""
    logger.info("Starting budget_status with event: %s", json.dumps(event))

    try:
        user_id = event['requestContext']['authorizer']['claims']['sub']
        logger.info("Checking budget status for user: %s", user_id)

        # Get all budgets
        budgets = budgets_table.query(
            KeyConditionExpression='userId = :uid',
            ExpressionAttributeValues={':uid': user_id}
        ).get('Items', [])

        budget_count = len(budgets)
        logger.info("Retrieved %d budgets", budget_count)

        # Get current month's transactions with IST timezone
        ist_timezone = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist_timezone)
        start_of_month = now.strftime('%Y-%m-01')
        end_of_month = now.strftime('%Y-%m-%d')

        logger.info("Using date range: %s to %s (IST)", start_of_month, end_of_month)

        transactions = transactions_table.query(
            KeyConditionExpression='userId = :uid',
            FilterExpression='#dt BETWEEN :start AND :end',
            ExpressionAttributeNames={'#dt': 'date'},
            ExpressionAttributeValues={
                ':uid': user_id,
                ':start': start_of_month,
                ':end': end_of_month
            }
        ).get('Items', [])

        transaction_count = len(transactions)
        logger.info("Retrieved %d transactions for period %s to %s",
                   transaction_count, start_of_month, end_of_month)

        # Calculate spending per category
        spending = defaultdict(decimal.Decimal)  # Use Decimal for precise calculations
        for t in transactions:
            amount = decimal.Decimal(str(t['amount']))  # Convert to Decimal safely
            spending[t['category']] += amount

        logger.debug("Monthly spending by category: %s",
                    json.dumps(dict(spending), cls=DecimalEncoder))

        # Compare with budgets
        status = []
        for budget in budgets:
            category = budget['category']
            limit = decimal.Decimal(str(budget['limit']))
            current = spending.get(category, decimal.Decimal('0'))
            percentage = (current / limit * 100) if limit > 0 else decimal.Decimal('0')

            status.append({
                'category': category,
                'limit': limit,
                'spent': current,
                'remaining': limit - current,
                'percentageUsed': percentage
            })

            if percentage >= 90:
                logger.warning("Budget nearly exceeded for category %s: %.2f%% used",
                             category, percentage)

        logger.info("Budget status analysis completed for %d categories", len(status))

        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'month': now.strftime('%Y-%m'),
                'budgetStatus': status
            }, cls=DecimalEncoder)
        }
    except Exception as e:
        logger.error("Error checking budget status: %s", str(e), exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }