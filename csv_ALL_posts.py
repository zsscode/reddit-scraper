# EXPORTS CSV FILE FOR *ALL* SPECIFIED POSTS
# expect runtime of ~30 minutes per 1000 posts scraped

import json
import praw
import pandas as pd
import datetime as dt
import requests
import textwrap
import time
import re 

start_time = time.time()

# load Reddit authentication for PRAW (not necessary if only using Pushshift)
# reference: https://www.storybench.org/how-to-scrape-reddit-with-python/
reddit = praw.Reddit(client_id='PERSONAL_USE_SCRIPT_14_CHARS', 
                     client_secret='SECRET_KEY_27_CHARS',
                     user_agent='YOUR_APP_NAME')

# -----------------------------------------------

# building the Pushshift URL 
keywords = 'bias|prejudice'
subs = 'AskSocialScience,AskFeminists' 
submission_fields = 'id,score,full_link,subreddit,title,selftext,created_utc,author,num_comments' 
posts_shown = 1000 # default size=25 (up to 1000)
earliest_date = 1546300800 # 12am 1/1/19 unix timestamp
aggs = '&aggs=subreddit,author' # set aggs = "" to exclude aggregation data (faster runtime)

# search submissions using Pushshift
# reference: https://github.com/pushshift/api#searching-submissions
url = f"https://api.pushshift.io/reddit/search/submission/?q={keywords}&subreddit={subs}&fields={submission_fields}&size={posts_shown}&after={earliest_date}&sort=desc&metadata=true{aggs}"

# -----------------------------------------------

# function that styles text for readability
def clean_text(text):
    text = text.strip()
    text = re.sub('\n+', '\n', text)
    text = re.sub('&amp;', '&', text)
    text = re.sub('&lt;', '<', text)
    text = re.sub('&gt;', '>', text)
    text = re.sub('&#x200B;', '', text)
    text = re.sub('&nbsp;', ' ', text)
    return text

# -----------------------------------------------

# paginating results to work around the 1000 size limit (gather data 1000 posts at a time)
start_from = ''
first_pass = True
data = []
while True:
    if first_pass: 
        request = requests.get(url+start_from+aggs)
        print("request made - first pass")
        posts = request.json()
        if aggs != '': # if collecting aggregate data, only collect once to reduce runtime
            author_summary = posts['aggs']['author']
            subreddit_summary = posts['aggs']['subreddit']
        first_pass = False
        print(keywords + ": " + str(posts['metadata']['total_results']))
    else:
        request = requests.get(url+start_from)
        print("request made")
        posts = request.json()
    
    # make sure Pushshift is gathering all Reddit data (IMPORTANT IF SCRAPING FOR RESEARCH)
    assert(posts['metadata']['shards']["successful"]==posts['metadata']['shards']["total"]) 
    
    data.extend(posts["data"])
    if len(posts["data"]) == 0:
		    break # stop collecting data once there's nothing left to collect
		
    last_utc = data[-1]['created_utc']
    start_from = '&before=' + str(last_utc)

print("successful data collection!")

# -----------------------------------------------

# clean/format data and update scores with PRAW for more up-to-date stats
for d in data:

    # get data from PRAW based on unique post ID from Pushshift
    submission = reddit.submission(id=d['id'])
    submission.comment_sort = 'top'

    d.update({'score': submission.score})
    d.update({'post keywords': keywords}) # for reference in csv
    d.update({'date': dt.datetime.fromtimestamp(d['created_utc']).date()})
    try:
        d.update({'comment_score': submission.comments[0].score})
        d.update({'top_comment': clean_text(submission.comments[0].body)})
    except:
        d.update({'comment_score': "N/A"})
        d.update({'top_comment': "N/A"})
    d.update({'title': clean_text(d.get("title","N/A"))})
    d.update({'selftext': clean_text(d.get("selftext","N/A"))})
	
# -----------------------------------------------
    
# final formatting and exporting to csv
df = pd.DataFrame.from_records(data, columns= ['full_link', 'subreddit', 'post keywords', 'id', 'date', 'score', 'num_comments', 'author', 'title', 'selftext', 'top_comment', 'comment_score'])
df = df.sort_values(['score', 'comment_score'], ascending=False) # sort by updated scores in csv
df.to_csv('./scraped_files/reddit_overview.csv', index=False, header=True)

if aggs != '': # if collecting aggregate data, export to separate csv files
    author_df = pd.DataFrame.from_records(author_summary, columns = ['key', 'doc_count'])
    author_df.rename({'key': 'author', 'doc_count': 'count'}, axis=1, inplace=True)
    author_df.to_csv('./scraped_files/author_summary.csv', index=False, header=True)

    subreddit_df = pd.DataFrame.from_records(subreddit_summary, columns = ['key', 'doc_count'])
    subreddit_df.rename({'key': 'subreddit', 'doc_count': 'count'}, axis=1, inplace=True)
    subreddit_df.to_csv('./scraped_files/subreddit_summary.csv', index=False, header=True)

print("---runtime: %s seconds ---" % (time.time() - start_time))
