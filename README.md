# hAIre - AI Recruitment Assistant

An intelligent aws-based recruitment system that accelerates talent discovery, improves job-candidate matching, and reduces hiring operational burden through AI technology.

## Overview

hAIre leverages AWS cloud services and AI capabilities to streamline the entire recruitment process:

- **Smart Screening**: AI-powered resume analysis and candidate ranking based on job requirements
- **Automated Workflow**: Seamless integration from job posting to candidate notification via EventBridge and Step Functions
- **Intelligent Matching**: Vector-based similarity matching using OpenSearch and Bedrock LLM services
- **Intelligent Notifications**: Automated alerts to hiring managers via SNS (Email/Teams/Slack)
- **Data-driven Insights**: Comprehensive recruitment analytics and performance tracking
- **Multi-role Support**: Tailored experiences for HR recruiters, hiring managers, and job seekers

## Key Features

- 📋 Bulk job posting and team information upload
- 🤖 AI-powered requirement extraction and confirmation
- 📄 Automated resume parsing and structured data storage
- 🎯 Advanced job-candidate compatibility scoring
- 📧 Instant notifications and tracking system
- 📊 Comprehensive recruitment dashboard and analytics

## Architecture

Built on AWS serverless architecture including Lambda, DynamoDB, S3, OpenSearch, Step Functions, and Bedrock AI services for scalable and secure recruitment management.