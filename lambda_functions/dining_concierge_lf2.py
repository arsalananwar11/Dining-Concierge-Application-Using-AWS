import json
import boto3
import logging
import os
import requests
import random
from lf2_helpers import *
import time

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

queue_url = os.environ['QUEUE_URL']
es_endpoint = os.environ['ES_ENDPOINT']
    
def lambda_handler(event, context):
    logger.info(event)
    result = poll_sqs_messages()
    if 'Messages' not in result:
        return {
            'statusCode': 200,
            'body': json.dumps('No messages in the queue')
        }

    for record in result['Messages']:
        logger.info(f"Record: {record}")
        user_dining_preferences = {
            'city': record['MessageAttributes']['city']['StringValue'].lower(),
            'date': record['MessageAttributes']['date']['StringValue'].lower(),
            'people': record['MessageAttributes']['people']['StringValue'].lower(),
            'phone_number': record['MessageAttributes']['phone_number']['StringValue'].lower(),
            'time': record['MessageAttributes']['time']['StringValue'].lower(),
            'cuisine': record['MessageAttributes']['cuisine']['StringValue'].lower(),
            'email': record['MessageAttributes']['email']['StringValue'].lower(),
        }
        
        logger.info(f"user_dining_preferences: {user_dining_preferences}")
        receipt_handle = record['ReceiptHandle']
            
        restaurants_list = get_restaurant_suggestions_based_on_cuisine(user_dining_preferences['cuisine'])
        restaurants_list = remove_duplicate_restaurants(restaurants_list)
        selected_restaurants = random.sample(restaurants_list, k = 5)
        logger.info(f"restaurant_list: {selected_restaurants}")
        restaurant_suggestion_list = get_restaurant_details(selected_restaurants)
        logger.info(f"restaurant_suggestion_list: {restaurant_suggestion_list}")
        send_mail_to_user_via_ses(restaurant_suggestion_list, user_dining_preferences)
        """
        create_or_update_users_past_suggestions(restaurants_list['Responses']['yelp-restaurants'], user_dining_preferences)
        """
        delete_sqs_message(receipt_handle)
    return {
        'statusCode': 200,
        'body': json.dumps('Successfully run the Dining Concierge LF2 Function')
    }
    
def poll_sqs_messages():
    logger.info(f"QUEUE_URL: {queue_url}")
    sqs = boto3.client('sqs')
    result = sqs.receive_message(
        QueueUrl = queue_url, 
        MaxNumberOfMessages=10,
        MessageAttributeNames=[
            'All'
        ],
        VisibilityTimeout=10,
        WaitTimeSeconds=0
        )

    return result
    
def delete_sqs_message(receipt_handle):
    sqs = boto3.client('sqs')
    try:
        response = sqs.delete_message(
            QueueUrl= queue_url,
            ReceiptHandle=receipt_handle
        )
        logger.info(f"Deleted Message from SQS: {response}")
    except Exception as e:
        logger.error(f"Error deleting message: {e}")
    
def get_restaurant_suggestions_based_on_cuisine(cuisine):
    host = os.environ.get('ES_HOST')
    url = f"{es_endpoint}/_search?q=cuisine:{cuisine}&size=10"
    response = requests.get(url, auth=(os.environ.get('ES_USERNAME'), os.environ.get('ES_PASSWORD'))) 
    restaurant_data = json.loads(response.text)
    restaurant_suggestion_list = []
    if restaurant_data['hits']['total']['value'] > 0:
        data_list = restaurant_data['hits']['hits']
        restaurant_suggestion_list = list(map(lambda x: x['_id'], data_list))
        
    return restaurant_suggestion_list
    
def remove_duplicate_restaurants(restaurant_suggestion_list):
    return list(set(restaurant_suggestion_list))
    
def get_restaurant_details(selected_restaurants):
    client = boto3.resource('dynamodb')
    restaurants_list = []
    restaurants_list = client.batch_get_item(
        RequestItems={
            'yelp-restaurants': {'Keys': [{'BusinessID': id} for id in selected_restaurants[:5]]}
        }
    )
    sorted_restaurants_list = sort_restaurants_by_rating(restaurants_list)
    return sorted_restaurants_list
    
def sort_restaurants_by_rating(restaurants_list):
    # Sort the list by 'Rating' in descending order
    sorted_restaurants = sorted(
        restaurants_list['Responses']['yelp-restaurants'], 
        key=lambda x: x['Rating'], 
        reverse=True
    )
    return sorted_restaurants

def send_mail_to_user_via_ses(restaurant_suggestion_list, user_dining_preferences):
    SENDER = os.environ['SES_FROM_EMAIL'] 
    RECIPIENT = user_dining_preferences['email']
    SUBJECT = "Restaurant Suggestion from Dining Concierge Service"
    CHARSET = "UTF-8"
    
    columns = ['Name', 'Address', 'Rating', 'Reviews']
    reordered_dicts = [reorder_dict(restaurant, columns) for restaurant in restaurant_suggestion_list]
    logger.info(f"reordered_dicts: {reordered_dicts}")
    BODY_HTML = create_email_body(reordered_dicts, user_dining_preferences)
    logger.info(f"BODY_HTML: {BODY_HTML}")
    
    client = boto3.client('ses')
    try:
        response = client.send_email(
            Destination={
                'ToAddresses': [
                    RECIPIENT,
                ],
            },
            Message={
                'Body': {
                    'Html': {
                        'Charset': 'UTF-8',
                        'Data': BODY_HTML,
                    },
                },
                'Subject': {
                    'Charset': 'UTF-8',
                    'Data': SUBJECT,
                },
            },
            Source=SENDER,
        )
    except Exception as e:
        logger.exception(e.response['Error']['Message'])
    
    else:
        print("Email sent! Message ID:"),
        logger.info(response['MessageId'])
    