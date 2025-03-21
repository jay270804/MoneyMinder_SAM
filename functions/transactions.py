import json
import boto3
import uuid
import os
from datetime import datetime
import decimal
import logging
import pytz

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Helper class for JSON serialization of Decimal types
class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            return float(o) if o % 1 != 0 else int(o)
        return super(DecimalEncoder, self).default(o)

# Initialize DynamoDB resource
dynamodb = boto3.resource('dynamodb')
transactions_table = dynamodb.Table(os.environ['TRANSACTIONS_TABLE'])
budgets_table = dynamodb.Table(os.environ['BUDGETS_TABLE'])
sns = boto3.client('sns')

def create_transaction(event, context):
    """Create a new transaction and check budget status"""
    logger.info("Starting create_transaction with event: %s", json.dumps(event))

    try:
        # Parse request body
        body = json.loads(event['body'])
        # logger.debug("Request body: %s", json.dumps(body))

        # Get user ID from Cognito authorizer
        user_id = event['requestContext']['authorizer']['claims']['sub']
        # Get user email from Cognito claims
        user_email = event['requestContext']['authorizer']['claims']['email']
        # logger.info("Processing transaction for user: %s", user_id)

        # Get current time in IST
        ist_timezone = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist_timezone)

        # Use IST timestamp for transaction creation
        transaction = {
            'userId': user_id,
            'transactionId': str(uuid.uuid4()),
            'amount': decimal.Decimal(str(body.get('amount'))),
            'category': body.get('category'),
            'description': body.get('description'),
            'date': body.get('date') or now.strftime('%Y-%m-%d'),
            'createdAt': now.strftime('%Y-%m-%dT%H:%M:%S%z'),
            'paymentMethod': body.get('paymentMethod', 'other'),
        }
        # logger.debug("Prepared transaction: %s", json.dumps(transaction, cls=DecimalEncoder))

        # Store transaction in DynamoDB
        transactions_table.put_item(Item=transaction)
        # logger.info("Transaction stored successfully with ID: %s", transaction_id)

        # Check budget status - pass user email for SES
        # check_budget(user_id, body['category'], body['amount'], user_email)
        # logger.info("Budget check completed for category: %s", body['category'])

        return {
            'statusCode': 201,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'message': 'Transaction created successfully',
                'transactionId': transaction['transactionId']
            })
        }
    except Exception as e:
        logger.error("Error creating transaction: %s", str(e), exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }

def get_transactions(event, context):
    """Get transactions for a user with optional filtering"""
    logger.info("Starting get_transactions with event: %s", json.dumps(event))

    try:
        # Get user ID from Cognito authorizer
        user_id = event['requestContext']['authorizer']['claims']['sub']
        logger.info("Retrieving transactions for user: %s", user_id)

        # Get query parameters
        params = event.get('queryStringParameters', {}) or {}
        logger.debug("Query parameters: %s", json.dumps(params))

        # Update default date range to use IST
        ist_timezone = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist_timezone)

        start_date = params.get('startDate', now.strftime('%Y-%m-01'))
        end_date = params.get('endDate', now.strftime('%Y-%m-%d'))
        logger.info("Fetching transactions from %s to %s (IST)", start_date, end_date)

        # Prepare query
        query_params = {
            'KeyConditionExpression': 'userId = :uid',
            'ExpressionAttributeValues': {
                ':uid': user_id
            },
            'ScanIndexForward': False  # Most recent first
        }

        # Handle category filter
        if 'category' in params:
            logger.info("Filtering by category: %s", params['category'])
            # Use the category index
            query_params['IndexName'] = 'CategoryIndex'
            query_params['KeyConditionExpression'] = 'userId = :uid AND category = :cat'
            query_params['ExpressionAttributeValues'][':cat'] = params['category']

        # Handle date filtering
        if 'startDate' in params:
            start_date = params['startDate']
            logger.info("Filtering by start date: %s", start_date)
            # Add filter for dates
            filter_expr = 'date >= :start'
            query_params['ExpressionAttributeValues'][':start'] = start_date

            if 'FilterExpression' in query_params:
                query_params['FilterExpression'] += f' AND {filter_expr}'
            else:
                query_params['FilterExpression'] = filter_expr

        if 'endDate' in params:
            end_date = params['endDate']
            logger.info("Filtering by end date: %s", end_date)
            # Add filter for dates
            filter_expr = 'date <= :end'
            query_params['ExpressionAttributeValues'][':end'] = end_date

            if 'FilterExpression' in query_params:
                query_params['FilterExpression'] += f' AND {filter_expr}'
            else:
                query_params['FilterExpression'] = filter_expr

        logger.debug("Final query parameters: %s", json.dumps(query_params))

        # Execute query
        response = transactions_table.query(**query_params)
        item_count = len(response.get('Items', []))
        logger.info("Query returned %d items", item_count)

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'transactions': response.get('Items', []),
                'count': item_count,
                'lastEvaluatedKey': response.get('LastEvaluatedKey')
            }, cls=DecimalEncoder)
        }
    except Exception as e:
        logger.error("Error retrieving transactions: %s", str(e), exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }

def check_budget(user_id, category, amount, user_email):
    """Check if a transaction exceeds the user's budget"""
    logger.info("Checking budget for user %s, category %s, amount %s", user_id, category, amount)

    try:
        # Get budget for this category
        response = budgets_table.get_item(
            Key={
                'userId': user_id,
                'category': category
            }
        )

        # If no budget exists, return
        if 'Item' not in response:
            logger.info("No budget found for category: %s", category)
            return

        budget = response['Item']
        budget_limit = budget['limit']
        logger.debug("Found budget: %s", json.dumps(budget, cls=DecimalEncoder))

        # Use IST timezone for current month calculation
        ist_timezone = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist_timezone)
        current_month = now.strftime('%Y-%m')
        logger.info("Checking budget for month: %s (IST)", current_month)

        # Query transactions in this category for current month
        response = transactions_table.query(
            IndexName='CategoryIndex',
            KeyConditionExpression='userId = :uid AND category = :cat',
            FilterExpression='begins_with(#dt, :month)',
            ExpressionAttributeNames={
                '#dt': 'date'
            },
            ExpressionAttributeValues={
                ':uid': user_id,
                ':cat': category,
                ':month': current_month
            }
        )

        # Calculate total spent
        total_spent = sum(item['amount'] for item in response.get('Items', []))
        # logger.info("Total spent in %s for category %s: %s", current_month, category, total_spent)

        # Check if budget exceeded
        if total_spent > budget_limit:
            # logger.warning("Budget exceeded for category %s. Spent: %s, Limit: %s",
            #              category, total_spent, budget_limit)

            # Get SES client
            ses = boto3.client('ses')

            # Prepare email content
            sender_email = os.environ['SES_SENDER_EMAIL']
            subject = 'MoneyMinder Budget Alert'
            body_text = f"Budget Alert: You've spent ${total_spent} on {category}, exceeding your budget of ${budget_limit}"
            body_html = f"""
            <html>
            <head></head>
            <body>
              <h1>MoneyMinder Budget Alert</h1>
              <p>You've spent <strong>${total_spent}</strong> on <strong>{category}</strong>.</p>
              <p>This exceeds your budget of <strong>${budget_limit}</strong>.</p>
              <p>Log in to your MoneyMinder account to review your spending and adjust your budget if needed.</p>
            </body>
            </html>
            """

            # Send email using SES
            try:
                response = ses.send_email(
                    Source=sender_email,
                    Destination={
                        'ToAddresses': [user_email]
                    },
                    Message={
                        'Subject': {
                            'Data': subject
                        },
                        'Body': {
                            'Text': {
                                'Data': body_text
                            },
                            'Html': {
                                'Data': body_html
                            }
                        }
                    }
                )
                # logger.info("Budget alert email sent with MessageId: %s", response['MessageId'])
            except Exception as e:
                logger.error("Error sending email: %s", str(e))

            # Update budget item with alert status
            # budgets_table.update_item(
            #     Key={
            #         'userId': user_id,
            #         'category': category
            #     },
            #     UpdateExpression='SET alertSent = :val',
            #     ExpressionAttributeValues={
            #         ':val': True
            #     }
            # )
            # logger.info("Budget alert status updated")

    except Exception as e:
        logger.error("Error checking budget: %s", str(e), exc_info=True)