# 💰 MoneyMinder - Serverless Expense Tracking & Budget Management

[![AWS Serverless](https://img.shields.io/badge/AWS-Serverless-orange?logo=amazon-aws)](https://aws.amazon.com/serverless)
[![SAM Deployable](https://img.shields.io/badge/Deploy-SAM-yellowgreen)](https://aws.amazon.com/serverless/sam/)

A modern serverless application for personal finance management featuring budget alerts, spending analytics, and secure transaction tracking. Built with AWS Serverless Application Model (SAM) and best-in-class AWS services.

## 🌟 Key Features

- **Expense Tracking**: Record transactions with category, amount, and payment method
- **Budget Management**: Set monthly budgets per category with automatic alerts
- **Real-time Analytics**: Spending breakdowns by category/time period
- **Email Notifications**: SES-powered budget limit alerts
- **Secure Auth**: Cognito user authentication with email verification
- **Responsive Web UI**: S3-hosted static website with CI/CD ready
- **Cost Effective**: Pay-per-use pricing with AWS serverless services

## 🛠️ Tech Stack

**AWS Services** | **Frameworks/Libraries**
--- | ---
λ Lambda (Python 3.12) | ⚡ AWS SAM
🚪 API Gateway | 🗄️ DynamoDB
🔐 Cognito | 📧 SES
📦 S3 | 📊 CloudFormation
⚙️ CloudWatch | 🛡️ IAM

## 📂 Project Structure

```
moneyminder/
├── functions/           # Lambda handlers
│   ├── analytics.py     # Spending analysis
│   ├── budgets.py       # Budget management
│   └── transactions.py  # CRUD operations
├── events/              # Test payloads
├── tests/               # Unit & integration tests
├── template.yaml        # SAM infrastructure
└── samconfig.toml       # Deployment config
```

## 🚀 Deployment

### Prerequisites
- AWS Account with CLI configured
- SAM CLI ([Install](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html))
- Docker (for local testing)
- Python 3.12

```
# Build & deploy
sam build --use-container
sam deploy --guided

# First-time deployment will prompt for:
# - Stack name: "MoneyMinder"
# - AWS Region: (your preferred region)
# - SES Sender Email: your-verified-email@domain.com
```

## 🔧 Configuration

### Environment Variables
```
Globals:
  Function:
    Environment:
      Variables:
        TRANSACTIONS_TABLE: !Ref TransactionsTable
        BUDGETS_TABLE: !Ref BudgetsTable
        SES_SENDER_EMAIL: !Ref SenderEmailParameter
```

### Customizable Parameters
```
Parameters:
  SenderEmailParameter:
    Type: String
    Description: Verified SES sender email
    Default: your-email@domain.com
```

## 📡 API Endpoints

| Method | Path                    | Description                     | Lambda Function          |
|--------|-------------------------|---------------------------------|--------------------------|
| POST   | /transactions           | Create new transaction          | CreateTransactionFunction|
| GET    | /transactions           | List filtered transactions      | GetTransactionsFunction  |
| POST   | /budgets                | Create/update budget            | CreateBudgetFunction     |
| GET    | /budgets                | List user budgets               | GetBudgetsFunction       |
| GET    | /analytics/spending     | Spending analysis by category    | AnalyzeSpendingFunction  |
| GET    | /analytics/budget-status| Current budget utilization       | BudgetStatusFunction     |

## 🧪 Testing

```
# Unit tests
pip install -r tests/requirements.txt
python -m pytest tests/unit -v

# Integration tests (after deployment)
AWS_SAM_STACK_NAME="MoneyMinder" python -m pytest tests/integration -v

# Local API testing
sam local start-api
curl http://localhost:3000/transactions
```

## 🧹 Cleanup

```
sam delete --stack-name MoneyMinder
```
