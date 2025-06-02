import os
import boto3
import logging
from opensearchpy import OpenSearch, AWSV4SignerAuth
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

def get_opensearch_client():
    logger.info("Initializing OpenSearch client")
    host = os.getenv("OPENSEARCH_HOST", "localhost")
    port = int(os.getenv("OPENSEARCH_PORT", 9200))
    use_aws = os.getenv("USE_AWS", "false").lower() == "true"
    verify_certs = os.getenv("VERIFY_CERTS", "false").lower() == "true"
    
    # Construct the full URL
    url = f"https://{host}:{port}"
    logger.info(f"Connecting to OpenSearch at {url}")
    logger.info(f"Using AWS credentials: {use_aws}")
    logger.info(f"SSL certificate verification: {verify_certs}")
    
    try:
        if use_aws:
            session = boto3.Session()
            credentials = session.get_credentials()
            auth = AWSV4SignerAuth(credentials, session.region_name)
            client = OpenSearch(
                hosts=[url],
                http_auth=auth,
                use_ssl=True,
                verify_certs=verify_certs,
                ssl_show_warn=False
            )
            logger.info("Successfully created OpenSearch client with AWS credentials")
        else:
            username = os.getenv("OPENSEARCH_USERNAME", "admin")
            password = os.getenv("OPENSEARCH_PASSWORD", "admin")
            client = OpenSearch(
                hosts=[url],
                http_auth=(username, password),
                use_ssl=True,
                verify_certs=verify_certs,
                ssl_show_warn=False
            )
            logger.info("Successfully created OpenSearch client with username/password")
        
        # Test the connection
        client.info()
        logger.info("Successfully connected to OpenSearch")
        return client
    except Exception as e:
        logger.error(f"Failed to create OpenSearch client: {str(e)}")
        raise 