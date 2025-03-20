import json
import boto3
import os
import decimal
from datetime import datetime
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
budgets_table = dynamodb.Table(os.environ['BUDGETS_TABLE'])

def create_budget(event, context):
    """Create or update a budget for a user"""
    logger.info("Starting create_budget with event: %s", json.dumps(event))

    try:
        # Parse request body
        body = json.loads(event['body'])
        logger.debug("Request body: %s", json.dumps(body))

        # Get user ID from Cognito authorizer
        user_id = event['requestContext']['authorizer']['claims']['sub']
        logger.info("Processing budget for user: %s", user_id)

        category = body['category']
        budget_limit = decimal.Decimal(str(body['limit']))
        logger.info("Setting budget for category %s with limit %s", category, budget_limit)

        # Get current time in IST
        ist_timezone = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist_timezone)

        budget = {
            'userId': user_id,
            'category': category,
            'limit': budget_limit,
            'createdAt': now.strftime('%Y-%m-%dT%H:%M:%S%z'),
            'updatedAt': now.strftime('%Y-%m-%dT%H:%M:%S%z')
        }
        logger.debug("Prepared budget item: %s", json.dumps(budget, cls=DecimalEncoder))

        # Save to DynamoDB
        budgets_table.put_item(Item=budget)
        logger.info("Budget saved successfully for category: %s", category)

        return {
            'statusCode': 201,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'message': 'Budget created/updated successfully',
                'category': category
            }, cls=DecimalEncoder)
        }
    except Exception as e:
        logger.error("Error creating budget: %s", str(e), exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': f'Error creating budget: {str(e)}'
            })
        }

def get_budgets(event, context):
    """Retrieve all budgets for a user"""
    logger.info("Starting get_budgets with event: %s", json.dumps(event))

    try:
        # Get user ID from Cognito authorizer
        user_id = event['requestContext']['authorizer']['claims']['sub']
        logger.info("Retrieving budgets for user: %s", user_id)

        # If you have any date filtering, update it to use IST
        ist_timezone = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist_timezone)
        current_month = now.strftime('%Y-%m')

        # Query budgets for user
        response = budgets_table.query(
            KeyConditionExpression='userId = :uid',
            ExpressionAttributeValues={
                ':uid': user_id
            }
        )

        item_count = len(response.get('Items', []))
        logger.info("Retrieved %d budgets for user", item_count)
        logger.debug("Budget items: %s", json.dumps(response.get('Items', []), cls=DecimalEncoder))

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'budgets': response.get('Items', []),
                'count': item_count
            }, cls=DecimalEncoder)
        }
    except Exception as e:
        logger.error("Error retrieving budgets: %s", str(e), exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': f'Error retrieving budgets: {str(e)}'
            })
        }