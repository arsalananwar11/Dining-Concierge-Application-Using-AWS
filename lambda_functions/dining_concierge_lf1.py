import json
import logging
import os
import time
import dateutil.parser
import datetime
import boto3
from uuid import uuid4
import re


logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
sqs = boto3.client('sqs')
QUEUE_URL = 'https://sqs.us-east-1.amazonaws.com/156041420494/DiningConciergeMessageQueue.fifo'

def lambda_handler(event, context):
    """
    Based on the intent, the incoming request is routed to the respective handler.
    """
    os.environ['TZ'] = 'America/New_York'
    time.tzset()
    logger.debug(f"Invocation Source: ({event['invocationSource']})")
    return handle_event(event)
    
def handle_event(event):
    """
    Called when the user specifies an intent for this bot.
    """
    intent_name = event['sessionState']['intent']['name']
    logger.debug(f"Intent Name: { intent_name }")

    # Handle events/requests based on the intent
    if intent_name == 'GreetingIntent':
        return handle_greetings_intent(event)
    elif intent_name == 'DiningSuggestionsIntent':
        return handle_dining_suggestions_intent(event)
    elif intent_name == 'ThankYouIntent':
        return handle_thank_you(event)

    raise Exception('Intent with name ' + intent_name + ' not supported')

def handle_greetings_intent(event):
    """
    Handles the initial greeting
    """
    logger.debug(f"Recieved GreetingIntent with the following request details:\n{ json.dumps(event) }")

    session_attributes = event.get('sessionAttributes') if event.get(
        'sessionAttributes') is not None else {}
    return close_request(
        session_attributes,
        'Fulfilled',
        {
            'contentType': 'PlainText',
            'content': 'Hi there, I am your Dining Concierge Bot, how can I help?'
        },
        event['sessionState']['intent']['name']
    )
    
def handle_dining_suggestions_intent(event):
    """
    Handles the dining suggestions intent
    """
    logger.debug(f"Recieved DiningSuggestionsIntent with the following request details:\n{ json.dumps(event) }")
    slots = event["sessionState"]["intent"]["slots"]
    city = slots.get('city', None)
    cuisine = slots.get('cuisine', None)
    date = slots.get('date', None)
    time = slots.get('time', None)
    people = slots.get('people', None)
    phone_number = slots.get('phone_number', None)
    email = slots.get('email', None)

    session_attributes = event.get('sessionAttributes') if event.get(
        'sessionAttributes') is not None else {}
        
    if event['invocationSource'] == 'DialogCodeHook':
        validation_result = validate_dining(
            event['sessionState']['intent']['slots'])
        if not validation_result['isValid']:
            slots = event['sessionState']['intent']['slots']
            slots[validation_result['violatedSlot']] = None
        
            return elicit_slot(
                session_attributes,
                event['sessionState']['intent']['name'],
                slots,
                validation_result['violatedSlot'],
                validation_result['message'],
            )

        # send_message(city, cuisine, date, time, people, phone_number, email, request_id=event['sessionState']['originatingRequestId'])
        return delegate(
            session_attributes, 
            event['sessionState']['intent']['slots'],
            event['sessionState']['intent']['name']
        )
    elif event['invocationSource'] == "FulfillmentCodeHook":
        send_message(city, cuisine, date, time, people, phone_number, email, request_id=event['sessionState']['originatingRequestId'])
        return close_request(
            session_attributes,
            "Fulfilled",
            {
                'contentType': 'PlainText',
                'content': "Thanks, you're all set! You should receive my suggestions via email in a few minutes!"
            },
            event['sessionState']['intent']['name'],
        )
        
def handle_thank_you(intent_request: dict) -> dict:
    session_attributes = intent_request.get('sessionAttributes') if intent_request.get(
        'sessionAttributes') is not None else {}
    return close(
        session_attributes,
        "Fulfilled",
        {
            "contentType": "PlainText",
            "content": "You’re welcome boss! Thanks for chatting with us!"
        },
        intent_request['sessionState']['intent']['name']
    )

def close_request(session_attributes, fulfillment_state, message, intent_name):
    logger.debug(f"Closing { intent_name }")
    
    response = {
        'sessionState': {
            'sessionAttributes': session_attributes,
            'dialogAction': {
                'type': 'Close'
            },
            'intent': {
                'name': intent_name,
                'state': fulfillment_state
            },
        },
        'messages': [
            message
        ]
    }

    return response
    
def delegate(session_attributes, slots, intent):
    return {
        "sessionState": {
            'sessionAttributes': session_attributes,
            'dialogAction': {
                'type': 'Delegate',
            },
            "intent": {
                "name": intent,
                "slots": slots,
                "state": "ReadyForFulfillment",
            }
        }
    }
    
def validate_dining(slots: dict) -> dict:
    city = slots.get('city', None)
    cuisine = slots.get('cuisine', None)
    date = slots.get('date', None)
    time = slots.get('time', None)
    people = slots.get('people', None)
    phone_number = slots.get('phone_number', None)
    email = slots.get('email', None)

    if city and not is_valid_city(city['value']['interpretedValue']):
        return build_validation_result(
            False,
            "city",
            f"We currently do not provide suggestions for { city['value']['interpretedValue'] }. We only support New York (New York, Manhattan, Brooklyn) region. Which location do you want to book for?"
        )

    if cuisine and not is_valid_cuisine(cuisine['value']['interpretedValue']):
        return build_validation_result(
            False,
            "cuisine",
            f"We currently do not offer { cuisine['value']['interpretedValue'] } cuisine. We recommend 'indian', 'italian', 'chinese', 'mexican', 'japanese' cuisines. Can you try a different one?"
        )

    if date:
        if not is_valid_date(date['value']['interpretedValue']):
            return build_validation_result(
                False, 
                'date', 
                'Please enter a valid reservation date. When would you like to make your reservation?'
            )
        if datetime.datetime.strptime(date['value']['interpretedValue'], '%Y-%m-%d').date() <= datetime.date.today():
            return build_validation_result(
                False, 
                'date', 
                'Can you please provide a dining date in the future?'
            )

    if people is not None and (int(people['value']['interpretedValue']) < 1 or int(people['value']['interpretedValue']) > 10):
        return build_validation_result(
            False,
            'people',
            'We accept reservations from 1 to 10 guests only. Can you check and specify how many guests will be attending?'
        )
        
    """
    if email is not None and not is_valid_email(email):
        return build_validation_result(
            False,
            'email',
            'Please provide a valid email address'
        )
    """

    return {'isValid': True}
    
def elicit_slot(session_attributes, intent_name, slots, slot_to_elicit, message):
    response = {
        'sessionState': {
            'sessionAttributes': session_attributes,
            'dialogAction': {
                'type': 'ElicitSlot',
                'slotToElicit': slot_to_elicit,
            },
            'intent': {
                'name': intent_name,
                "slots": slots,
            }
        },
        'messages': [
            {
                "contentType": "PlainText",
                "content": message
            }
        ]
    }
    
    print(response)
    return response
    
def build_validation_result(isvalid, violated_slot, message_content):
    return {
        'isValid': isvalid,
        'violatedSlot': violated_slot,
        'message': message_content
    }
    
def is_valid_city(city):
    valid_cities = ['new york', 'manhattan', 'brooklyn', 'nyc']
    return city.lower() in valid_cities


def is_valid_cuisine(cuisine):
    valid_cuisines = ['indian', 'italian', 'chinese', 'mexican', 'japanese']
    return cuisine.lower() in valid_cuisines
    
def is_valid_date(date):
    try:
        dateutil.parser.parse(date)
        return True
    except ValueError:
        return False
        
def is_valid_email(email):
    email_regex = r"[^@]+@[^@]+\.[^@]+"
    if not re.match(email_regex, email):
        return False
    else:
        return True
        
def send_message(city, cuisine, date, time, people, phone_number, email, request_id=None) -> None:
    sqs = boto3.client('sqs')
    logger.debug(f"City: {city}\n Cuisine: {cuisine}\n")
    sqs_response = sqs.send_message(
        QueueUrl=QUEUE_URL,
        MessageAttributes={
            "city": {
                "DataType": "String",
                "StringValue": city["value"]["interpretedValue"],
            },
            "cuisine": {
                "DataType": "String",
                "StringValue": cuisine["value"]["interpretedValue"],
            },
            "date": {
                "DataType": "String",
                "StringValue": str(date["value"]["interpretedValue"]),
            },
            "people": {
                "DataType": "Number",
                "StringValue": people["value"]["interpretedValue"],
            },
            "phone_number": {
                "DataType": "String",
                "StringValue": phone_number["value"]["interpretedValue"],
            },
            "email": {
                "DataType": "String",
                "StringValue": email["value"]["interpretedValue"],
            },
            "time": {
                "DataType": "String",
                "StringValue": time["value"]["interpretedValue"],
            },
        },
        MessageBody=f"Dining Suggestions required for Cuisine:{cuisine['value']['interpretedValue']} in City:{city['value']['interpretedValue']}",
        MessageGroupId=request_id,
        MessageDeduplicationId=str(uuid4()),
    )

    logger.debug(f"SQS Response: { sqs_response }")