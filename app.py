from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
from opensearch_client import get_opensearch_client
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='static')
CORS(app)

# Initialize OpenSearch client
opensearch_client = get_opensearch_client()

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/search')
def search():
    query = request.args.get('q', '')
    logger.info(f"Received search request with query: {query}")
    
    if len(query) < 3:
        logger.info("Query too short, returning empty results")
        return jsonify({"results": []})
    
    try:
        # Query the smart_search_alias for autocomplete results
        search_query = {
            "size": 10,
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["*"],
                    "type": "best_fields"
                }
            }
        }
        
        logger.info(f"Executing search query: {search_query}")
        response = opensearch_client.search(
            index="smart_search_alias",
            body=search_query
        )
        
        hits = response.get("hits", {}).get("hits", [])
        logger.info("response from opensearch ")
        results = []
        
        for hit in hits:
            try:
                source = hit.get("_source", {})
                index_name = hit.get("_index", "")
                result = {
                    "id": hit.get("_id", ""),
                    "type": "member" if index_name == "member_1" else "plan",
                    "data": source,
                    "index": index_name
                }
                # Log each result for debugging
                logger.info(f"Processing result: {result}")
                results.append(result)
            except Exception as e:
                logger.error(f"Error processing hit: {str(e)}")
                continue
        
        logger.info(f"Search completed successfully. Found {len(results)} results")
        return jsonify({"results": results})
    except Exception as e:
        logger.error(f"Error during search: {str(e)}")
        return jsonify({"error": str(e), "results": []}), 500

def get_ml_summary(data):
    """
    Get a summarized version of the data using the ML model.
    
    Args:
        data: The data to be summarized
        
    Returns:
        str: The summarized text or error message if summarization fails
    """
    
    try:
        ml_response = opensearch_client.transport.perform_request(
            'POST',
            '/_plugins/_ml/models/rluzGZcBSgqcBodJYVXj/_predict',
            body={
                "parameters": {
                    "messages": [
                        {
                            "role": "system",
                            "content": "Summarize the json response to a user readable format so that it can be displayed in a chat interface. If the data is a member, display the communication events on top of the member data in the summary."
                        },
                        {
                            "role": "user",
                            "content": str(data)
                        }
                    ]
                }
            }
        )
        logger.info(f"ML response: {ml_response}")
        summary = ml_response.get('inference_results', [{}])[0].get('output', [{}])[0].get('dataAsMap', {}).get('choices', [{}])[0].get('message', {}).get('content', '')
 
        return summary
    except Exception as e:
        logger.error(f"Error getting ML summary: {str(e)}")
        return "Unable to generate summary"

def get_member_communication_events(member_id):
    """
    Get communication events for a member.
    
    Args:
        member_id: The member ID to search for
        
    Returns:
        list: List of communication events or empty list if none found
    """
    try:
        search_query = {
            "size": 5,  # Adjust size as needed
            "query": {
                "term": {
                    "member_id": member_id
                }
            },
            "sort": [
                {"last_updated": {"order": "desc"}}
            ]
        }
       
        response = opensearch_client.search(
            index="member_communication_events",
            body=search_query
        )
        
        return response.get("hits", {}).get("hits", [])
    except Exception as e:
        logger.error(f"Error fetching communication events for member {member_id}: {str(e)}")
        return []

@app.route('/details')
def get_details():
    id = request.args.get('id')
    type = request.args.get('type')
    index = request.args.get('index')
    logger.info(f"Received details request for id: {id}, type: {type}, index: {index}")
    
    if type not in ["member", "plan"]:
        logger.error(f"Invalid type requested: {type}")
        return jsonify({"error": "Invalid type"}), 400
    
    # Determine the index based on type
    if not index:
        index = "member_1" if type == "member" else "plan_1"
    
    try:
        logger.info(f"Fetching details from index: {index}, id: {id}")
        if not id:
            logger.error("No ID provided")
            return jsonify({"error": "No ID provided"}), 400
            
        response = opensearch_client.get(index=index, id=id)
        source_data = response.get("_source", {})
        communication_events = []
        
        if index == "member_1":
            communication_events = get_member_communication_events(source_data.get("member_id"))
            if communication_events:
                # Create a combined data structure
                combined_data = {
                    "communication_events": [event["_source"] for event in communication_events],
                    "member_data": source_data                    
                }
                logger.info(f"Combined data: {combined_data}")
                summary = get_ml_summary(combined_data)
            else:
                summary = get_ml_summary(source_data)
        else:
            summary = get_ml_summary(source_data)
        
        logger.info(f"Successfully retrieved details for {type} with id {id}")
        return jsonify({
            "summary": summary,
            "details": source_data
        })
    except Exception as e:
        logger.error(f"Error fetching details from {index} with id {id}: {str(e)}")
        if "NotFoundError" in str(e):
            return jsonify({"error": f"Record not found in {index}"}), 404
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=8000) 