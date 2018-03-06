import os
import time
import re
from slackclient import SlackClient
from apiclient.discovery import build
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.errors import HttpError

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pylab as pl
import matplotlib.lines as ln
import matplotlib.pyplot as plt
import textwrap

# instantiate Slack client
slack_client = SlackClient(os.environ.get('SLACK_BOT_TOKEN'))
# starterbot's user ID in Slack: value is assigned after the bot starts up
starterbot_id = None

# constants
RTM_READ_DELAY = 1 # 1 second delay between reading from RTM
EXAMPLE_COMMAND = "do"
MENTION_REGEX = "^<@(|[WU].+?)>(.*)"

def parse_bot_commands(slack_events):
    """
        Parses a list of events coming from the Slack RTM API to find bot commands.
        If a bot command is found, this function returns a tuple of command and channel.
        If its not found, then this function returns None, None.
    """
    for event in slack_events:
        if event["type"] == "message" and not "subtype" in event:
            user_id, message = parse_direct_mention(event["text"])
            if user_id == starterbot_id:
                return message, event["channel"]
    return None, None

def parse_direct_mention(message_text):
    """
        Finds a direct mention (a mention that is at the beginning) in message text
        and returns the user ID which was mentioned. If there is no direct mention, returns None
    """
    matches = re.search(MENTION_REGEX, message_text)
    # the first group contains the username, the second group contains the remaining message
    return (matches.group(1), matches.group(2).strip()) if matches else (None, None)

def count(metric, command):
    SDate = "7daysAgo"
    EDate = "today"
    words = command.split(' ')
    if 'from' in command:
        pos = words.index('from')
        SDate = command.split()[pos+1]
    if 'to' in command:
        pos = words.index('to')
        EDate = command.split()[pos+1]
    analytics = initialize_analyticsreporting()
    response = analytics.reports().batchGet(
        body={
            'reportRequests': [
            {
                'viewId': VIEW_ID,
                'dateRanges': [{'startDate': SDate, 'endDate': EDate}],
                'metrics': [{'expression': 'ga:{}'.format(metric)}]
            }]
        }
    ).execute()
    answer = response['reports'][0]['data']['totals'][0]['values'][0]
    return answer

def countXY(metric, dimension, command):
    SDate = "7daysAgo"
    EDate = "today"
    words = command.split(' ')
    if 'from' in command:
        pos = words.index('from')
        SDate = command.split()[pos+1]
    if 'to' in command:
        pos = words.index('to')
        EDate = command.split()[pos+1]
    analytics = initialize_analyticsreporting()
    response = analytics.reports().batchGet(
        body={
            'reportRequests': [
            {
                'viewId': VIEW_ID,
                'dateRanges': [{'startDate': SDate, 'endDate': EDate}],
                'metrics': [{'expression': 'ga:{}'.format(metric)}],
                'dimensions': [{'name':'ga:{}'.format(dimension)}]

            }]
        }
    ).execute()
    answer = response['reports'][0]['data']['rows']
    if not answer[0]['dimensions'][0].isdigit():
        answer = sorted(answer, key=lambda x: float(x['metrics'][0]['values'][0]), reverse=True)
    yArray=[]
    for step in range(0, len(answer)):
        yArray.append(float(answer[step]['metrics'][0]['values'][0]))

    xArray=[]
    for step in range(0, len(answer)):
        xArray.append(answer[step]['dimensions'][0])

    return xArray, yArray

def handle_command(command, channel):
    """
        Executes bot command if the command is known
    """
# Count command
    elif command.startswith("count"):
        metric = command.split()[1]
        response = '`{} pageviews!`'.format(count(metric, command))

    # Graph command
    elif command.split()[0] == 'graph':
        if len(command.split())>1:
            metric = command.split()[1]
            words = command.split(' ')
            if 'by' in command and len(command.split())>3:
                pos = words.index('by')
                dimension = command.split()[pos+1]
                x, y=countXY(metric, dimension, command)
                if not x[0].isdigit():
                    my_xticks = [x[0], x[1], x[2], x[3], x[4],  x[5],  x[6]]
                    my_xticks = [textwrap.fill(text,15) for text in my_xticks]
                    x = np.array([0, 1, 2, 3, 4, 5, 6])
                    plt.xticks(x, my_xticks, rotation=45)
                    y = np.array([y[0], y[1], y[2], y[3], y[4], y[5], y[6]])
                pl.plot(x, y, "r-") # plotting by columns
                plt.ylim(ymin=0)
                pl.grid(True, linestyle='-.')
                plt.xlabel(dimension.capitalize())
                plt.ylabel(metric.capitalize())
                plt.title(metric.capitalize()+' by '+dimension.capitalize())
                plt.tight_layout()
                pl.savefig("graph.png")
                slack_client.api_call('files.upload', channels=channel, filename='graph.png', file=open('graph.png', 'rb'))
                pl.close()
            else:
                response='`What should {} be graphed by?`'.format(metric)
        else:
            response='`Graph what?`'

    # Help command
    elif command.split()[0] == 'help':
        response = '`Count ____ (from ____ to ____)` \n`Graph ____[Metric] by ____[Dimension] (from ____ to ____)` \n`(Dates: today / yesterday / NdaysAgo / YYYY-MM-DD)` \n`(Metrics: pageviews / adsenserevenue / <https://developers.google.com/analytics/devguides/reporting/core/dimsmets|more...>)` \n`(Dimensions: day / source / author / <https://developers.google.com/analytics/devguides/reporting/core/dimsmets|more...>)`'
        
    # Sends the response back to the channel
    slack_client.api_call("chat.postMessage", channel=channel,
                          text=response, as_user=True)

if __name__ == "__main__":
    if slack_client.rtm_connect(with_team_state=False):
        print("Starter Bot connected and running!")
        # Read bot's user ID by calling Web API method `auth.test`
        starterbot_id = slack_client.api_call("auth.test")["user_id"]
        while True:
            command, channel = parse_bot_commands(slack_client.rtm_read())
            if command:
                handle_command(command, channel)
            time.sleep(RTM_READ_DELAY)
    else:
        print("Connection failed. Exception traceback printed above.")
