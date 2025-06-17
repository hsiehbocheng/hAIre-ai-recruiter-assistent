# Use the official AWS Lambda Python 3.9 base image
FROM public.ecr.aws/lambda/python:3.12

# Install Poppler utilities
RUN dnf -y install poppler-utils

# Install pdf2image and its dependencies
RUN pip install pdf2image boto3

# Copy function code
COPY lambda_function.py ${LAMBDA_TASK_ROOT}

# Set the CMD to your handler (could also be done as a parameter override outside of Dockerfile)
CMD ["lambda_function.lambda_handler"]