import json
from datetime import datetime
import os
from DiscordAlertsTrader.configurator import cfg 
from DiscordAlertsTrader.port_sim import custom_msg_fromdict

root_dir  =  os.path.abspath(os.path.dirname(__file__))

def serialize_message(message):
    serialized = {
        'created_at': str(message.created_at),
        'channel_id': message.channel.id,
        'author': {
            'id': message.author.id,
            'name': message.author.name,
            'discriminator': message.author.discriminator
        },
        'content': message.content
    }
    return serialized

def save_message(filename, message):
    serialized_message = serialize_message(message)
    with open(filename, 'w') as file:
        json.dump(serialized_message, file)

def load_message(filename):
    with open(filename, 'r') as file:
        serialized_message = json.load(file)

    created_at = datetime.fromisoformat(serialized_message['created_at'])
    channel_id = serialized_message['channel_id']
    author_id = serialized_message['author']['id']
    author_name = serialized_message['author']['name']
    author_discriminator = serialized_message['author']['discriminator']
    content = serialized_message['content']

    # Create new message object using the loaded data
    message = CustomMessage(
        created_at=created_at,
        channel_id=channel_id,
        author_id=author_id,
        author_name=author_name,
        author_discriminator=author_discriminator,
        content=content
    )
    return message

def make_message(content=None, cfg=cfg):
    message = load_message(root_dir+"/data/discord_message.json")
    if content is not None:
        message.content = content
    else:
        message.content = 'BTO 5 AI 25c 12/09 @ 1 <@&940418825235619910> swinging'
    author = "BestTrader#1234"
    message.author.name, message.author.discriminator = author.split("#")
    return message

# Save the message to a file
# save_message('tests/data/message.json', message)

# Load the message from the file
# loaded_message = load_message('tests/data/message.json')

