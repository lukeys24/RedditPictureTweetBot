import praw
import tweepy
import shutil
import requests
import time
import os
from PIL import Image
import datetime
import html


REDDIT_CLIENT_ID = ''
REDDIT_CLIENT_SECRET = ''
REDDIT_USERNAME = ''
REDDIT_PASSWORD = ''
REDDIT_USER_AGENT = ''

TWITTER_CONSUMER_KEY = ''
TWITTER_CONSUMER_SECRET = ''

TWITTER_ACCESS_TOKEN = ''
TWITTER_ACCESS_SECRET = ''

# We will analyze this Twitter user's tweets to avoid tweeting duplicates
TWITTER_USERNAME = ''

# Subreddit that we grab posts to tweet
REDDIT_SUBREDDIT = ''

# Added at the end of every tweet
TWEET_SIGNATURE = '#reddit #' + REDDIT_SUBREDDIT

# Delay interval for tweets (Recommended >= 5 to not get locked by twitter)
TWEET_MINUTES_DELAY = 5

# Minimum score for reddit post we approve
POST_FLOOR_SCORE = 150

# Returns praw object created w/client id/secret, reddit username/password and user agent
def set_praw(clientId, clientSecret, redditUsername, redditPassword, userAgent) :
    return praw.Reddit(client_id = clientId,
                     client_secret = clientSecret,
                     username = redditUsername,
                     password = redditPassword,
                     user_agent = userAgent)

# Returns tweepy object with consumer key/secret given by twitter
def set_tweepy(consumer_key, consumer_secret) :
    return tweepy.OAuthHandler(consumer_key, consumer_secret)

# Authenticates twitter api with passed in tokens given by twitter
def set_tweepy_access(auth, access_token, access_token_secret) :
    auth.set_access_token(access_token, access_token_secret)

# Returns a list of all tweets for a twitter user
def get_all_Tweets(twitterHandle) :
    # Grabs latest 200 tweets for the twitterHandle
    new_tweets = api.user_timeline(screen_name = twitterHandle, count = 200, tweet_mode = 'extended')

    # This will hold all tweets
    all_tweets = []
    all_tweets.extend(new_tweets)

    # Id of oldest tweet in new_tweets array minus one, since api.user_timeline(max_id = last_id) retrieves tweets <= last_id
    if (len(new_tweets) > 0) :
        last_id = new_tweets[-1].id

        # Loop while we still have tweets, then reload list with new 200 tweets
        while len(new_tweets) > 0:
            # Grab new 200 tweets from twitter account twitterHandle with id less than/equal to last_id
            new_tweets = api.user_timeline(screen_name = twitterHandle, count=200, max_id=last_id, tweet_mode = 'extended')

            # Add the new tweets to the list of all tweets
            all_tweets.extend(new_tweets)

            # Update the last id
            last_id = all_tweets[-1].id - 1

    return all_tweets

# Download the image using requests.get, with a custom header to avoid 429 error
def download_image(imageURL) :
    # Download the image
    custom_header = {'user-agent': 'RedditSpacePics /u/spacepictures123'}
    r = requests.get(imageURL, stream=True, headers = custom_header)

    # If we successfully get URL we save the image
    if r.status_code == 200:
        with open(fileSaveName, 'wb') as f:
            r.raw.decode_content = True
            shutil.copyfileobj(r.raw, f)
        return True
    else:
        print(r.status_code)
        return False

# Print about what was tweeted and when next tweet will occur
def print_tweet_info(tweet_text) :
    now = datetime.datetime.now()
    now_plus_delay = now + datetime.timedelta(minutes = TWEET_MINUTES_DELAY)
    now_plus_delay = now_plus_delay.strftime("%Y-%m-%d %H:%M:%S")
    print("Just tweeted - " + tweet_text)
    print("Next tweet will be tweeted at " + now_plus_delay)

# Adds tweets from list to set for looking up duplicates
# This method is sensitive to filtering, it assumes all
# tweets end in the same TWEET_SIGNATURE and has an image link
def add_tweets_set(set_of_tweets, list_of_tweets) :
    for tweets in list_of_tweets:
        # EXAMPLE tweets._json['full_text'] we will process
        # "Titan's Northern Lakes &amp; Summer Methane Rain Storms [2205x2092] #reddit #space https://t.co/tINEjr1uPd"

        # Cuts last 24 characters since it's an image link
        tweet_text = tweets._json['full_text'][:-24]

        # Cuts the hashtags added onto the end of tweets
        if TWEET_SIGNATURE in tweet_text:
            tweet_text = tweet_text[:-len(TWEET_SIGNATURE)]

        # Unescapes all escaped characters in the string, first ran into problem with "&amp;" for "&"
        tweet_text = html.unescape(tweet_text)

        # Add the tweet to our set for checking duplicates later
        set_of_tweets.add(tweet_text)

# Initalizes praw by using Reddit client ID/Secret, reddit Username/Password and userAgent
reddit = set_praw(REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET,REDDIT_USERNAME, REDDIT_PASSWORD, REDDIT_USER_AGENT)

# Initalizes tweepy with Twitter consumer Key/Secret and authenticates with Twitter user's access Token/Secret
auth = set_tweepy(TWITTER_CONSUMER_KEY, TWITTER_CONSUMER_SECRET)
set_tweepy_access(auth, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET)
api = tweepy.API(auth)

# Updates twitter profile description/bio to tell what subreddit we're pulling from
api.update_profile(description = "Pictures from various subreddits - Currently pulling pictures from /r/" + REDDIT_SUBREDDIT)

# Set the subreddit for posts to grab and tweet
subreddit = reddit.subreddit(REDDIT_SUBREDDIT)

# Retrieves all tweets (3200 limit) for a specific user
user_tweets = get_all_Tweets(TWITTER_USERNAME)

# Stores text for tweets in a set for looking up duplicate tweets
set_tweets = set()
add_tweets_set(set_tweets, user_tweets)

# Infinite loop that continuously grabs tweets 100 at a time
while (True) :
    # Loop through limit # of tweets from subreddit's hot/top/etc category, use limit = None for retrieve as many as possible
    for submission in subreddit.hot(limit = 100) :
        # Text that we will be tweeting
        text_to_tweet = submission.title + TWEET_SIGNATURE

        # Ensure our tweet meets 140 char limit, reddit post's score is >= our set score
        # and that we aren't duplicating a tweet
        if (len(text_to_tweet) <= 140  and submission.score >= POST_FLOOR_SCORE and submission.title not in set_tweets) :
            # Replace all '/' chars since replace method mistakes it for a directory
            fileSaveName = submission.title.replace("/", " ") + ".jpg"

            # If image download is success we continue
            if(download_image(submission.url)) :

                try:
                    # Checks to see if image is corrupted
                    verifyImage = Image.open(fileSaveName)

                    # Ensure image size is below twitter's max image size (3.07mb)
                    if (os.stat(fileSaveName).st_size < 3072000):
                         # Catches when there's a twitter 130 error
                        try :
                            # Attempts to tweet the image
                            api.update_with_media(fileSaveName, text_to_tweet)

                            # Information on what was tweeted and when the next one will be tweeted
                            print_tweet_info(text_to_tweet)

                            # Waits TWEET_MINUTES_DELAY minutes to tweet next tweet
                            time.sleep(TWEET_MINUTES_DELAY * 60)
                            
                        except tweepy.error.TweepError :
                            print("ERROR - Likely encountered twitter's 130 Error when trying to tweet image")
                            
                    else :
                        print("Did not tweet " + submission.title + " because image is too large")
                        
                except IOError:
                    print('This file is corrupted - ' + fileSaveName)

        else :
            # Prints reason why we didn't tweet the image based on the 3 cases
            if len(text_to_tweet) > 140 :
                print("We did not tweet " + submission.title + " because text is too long")
            elif submission.score < POST_FLOOR_SCORE :
                print("We did not tweet " + submission.title + " because reddit's post score is too low")
            elif submission.title in set_tweets :
                print("We did not tweet " + submission.title + " because it is a duplicate")
