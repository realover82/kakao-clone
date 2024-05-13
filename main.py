from youtube_transcript_api import YouTubeTranscriptApi
import re
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from bs4 import BeautifulSoup
from urllib.request import urlopen
import json


def get_video_data(url):
  html = urlopen(url).read()
  soup = BeautifulSoup(html, 'html.parser')

  video_data = []
  for script in soup.find_all('script'):
    if 'ytInitialData' in script.text:
      data = json.loads(
          re.search(r'var ytInitialData = ({.*?});', script.text).group(1))
      for item in data['contents']['twoColumnBrowseResultsRenderer']['tabs'][
          0]['tabRenderer']['content']['sectionListRenderer']['contents'][0][
              'itemSectionRenderer']['contents'][0][
                  'playlistVideoListRenderer']['contents']:
        video_id = item['playlistVideoRenderer']['videoId']
        video_title = item['playlistVideoRenderer']['title']['runs'][0]['text']
        video_data.append([f"https://youtu.be/{video_id}", video_title])
      break

  return video_data


def get_transcripts(video_data):
  for video in video_data:
    video_url, video_title = video
    video_id = video_url.split('/')[-1]

    try:
      transcript = YouTubeTranscriptApi.get_transcript(video_id,
                                                       languages=['ko'])
      script = ' '.join([item['text'] for item in transcript])
      video.append(script)
    except:
      try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id,
                                                         languages=['en'])
        script = ' '.join([item['text'] for item in transcript])
        video.append(script)
      except:
        video.append('')

  return video_data


def save_to_gsheet(video_data):
  scope = [
      'https://spreadsheets.google.com/feeds',
      'https://www.googleapis.com/auth/drive'
  ]
  creds = ServiceAccountCredentials.from_json_keyfile_name(
      'speechtotext-373201-69d9f0b377e2.json', scope)
  client = gspread.authorize(creds)
  sheet = client.open("test2").worksheet("c")
  # .worksheet("a")

  for video in video_data:
    sheet.append_row(video)


# 사용 예시
# playlist_url = "https://www.youtube.com/playlist?list=PLZHnYvH1qtOYPPHRaHf9yPQkIcGpIUpdL"
# playlist_url = "https://www.youtube.com/playlist?
# list=https://youtube.com/playlist?list=PL_yXkA4LrwxKKswPTUlnk59UcoQS6GdtE&si=XFpeaCdLI4N41mEm
playlist_url = "https://youtube.com/playlist?list=PL_yXkA4LrwxKKswPTUlnk59UcoQS6GdtE&si=XFpeaCdLI4N41mEm"

video_data = get_video_data(playlist_url)
print(f"Video data: {video_data}")

video_data_with_transcripts = get_transcripts(video_data)
print(f"Video data with transcripts: {len(video_data_with_transcripts)}")

save_to_gsheet(video_data_with_transcripts)
print("Video data saved to Google Sheet.")

# new
from googleapiclient.discovery import build
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# 구글 스프레드시트 API 인증
scope = [
    'https://spreadsheets.google.com/feeds',
    'https://www.googleapis.com/auth/drive'
]
creds = ServiceAccountCredentials.from_json_keyfile_name(
    'speechtotext-373201-69d9f0b377e2.json', scope)
# 'speechtotext-373201-69d9f0b377e2.json', scope)
client = gspread.authorize(creds)

# 스프레드시트 열기
# sheet = client.open('test2').c
sheet = client.open("test2").worksheet("d")
# 유튜브 API 클라이언트 빌드
youtube = build('youtube',
                'v3',
                developerKey='AIzaSyCl2Ter4VgOR6X_QfLOSJF2ZVsNrlompow')

# 검색어 설정
search_query = 'hollywood movie industry'

# 검색 결과 가져오기
search_response = youtube.search().list(q=search_query,
                                        part='snippet',
                                        type='video',
                                        maxResults=50).execute()

# 검색 결과에서 비디오 ID 가져오기
video_ids = [item['id']['videoId'] for item in search_response['items']]

# # 스프레드시트에 비디오 정보 저장
# row = 1
# for vid in video_ids:
#     video = youtube.videos().list(
#         part='snippet,contentDetails,statistics',
#         id=vid
#     ).execute()

#     vid_title = video['items'][0]['snippet']['title']
#     vid_url = f"https://www.youtube.com/watch?v={vid}"
#     vid_length = video['items'][0]['contentDetails']['duration']
#     vid_date = video['items'][0]['snippet']['publishedAt']
#     vid_views = video['items'][0]['statistics']['viewCount']

#     sheet.update_cell(row, 1, vid_url)
#     sheet.update_cell(row, 2, vid_title)
#     sheet.update_cell(row, 3, vid_length)
#     sheet.update_cell(row, 4, vid_date)
#     sheet.update_cell(row, 5, vid_views)

#     row += 1
# 스프레드시트에 비디오 정보 저장
##########################################
# row = 1
# for vid in video_ids:
#     try:
#         video = youtube.videos().list(
#             part='snippet,contentDetails,statistics',
#             id=vid
#         ).execute()

#         vid_title = video['items'][0]['snippet']['title']
#         vid_url = f"https://www.youtube.com/watch?v={vid}"
#         vid_length = video['items'][0]['contentDetails']['duration']
#         vid_date = video['items'][0]['snippet']['publishedAt']
#         vid_views = video['items'][0]['statistics']['viewCount']

#         sheet.update_cell(row, 1, vid_url)
#         sheet.update_cell(row, 2, vid_title)
#         sheet.update_cell(row, 3, vid_length)
#         sheet.update_cell(row, 4, vid_date)
#         sheet.update_cell(row, 5, vid_views)
#     except Exception as e:
#         print(f"Error occurred for video ID {vid}: {e}")
#         # 에러가 발생하면 빈 칸으로 채우고 다음으로 넘어감
#         sheet.update_cell(row, 1, '')
#         sheet.update_cell(row, 2, '')
#         sheet.update_cell(row, 3, '')
#         sheet.update_cell(row, 4, '')
#         sheet.update_cell(row, 5, '')

#     row += 1
################################################
# 스프레드시트에 비디오 정보 저장
# row = 1
# for vid in video_ids:
#     try:
#         video = youtube.videos().list(
#             part='snippet,contentDetails,statistics',
#             id=vid
#         ).execute()

#         vid_title = video['items'][0]['snippet']['title']
#         vid_url = f"https://www.youtube.com/watch?v={vid}"
#         vid_length = video['items'][0]['contentDetails']['duration']
#         vid_date = video['items'][0]['snippet']['publishedAt']
#         vid_views = video['items'][0]['statistics']['viewCount']

#         sheet.update_cell(row, 1, vid_url)
#         sheet.update_cell(row, 2, vid_title)
#         sheet.update_cell(row, 3, vid_length)
#         sheet.update_cell(row, 4, vid_date)
#         sheet.update_cell(row, 5, vid_views)
#     except Exception as e:
#         print(f"Error occurred for video ID {vid}: {e}")
#         continue

#     row += 1
################################
# row = 1
# for vid in video_ids:
#   try:
#     video = youtube.videos().list(part='snippet,contentDetails,statistics',
#                                   id=vid).execute()

#     if 'items' in video and video['items']:
#       vid_title = video['items'][0]['snippet']['title']
#       vid_url = f"https://www.youtube.com/watch?v={vid}"
#       vid_length = video['items'][0]['contentDetails']['duration']
#       vid_date = video['items'][0]['snippet']['publishedAt']
#       vid_views = video['items'][0]['statistics']['viewCount']
#       vid_id = vid  # 비디오 ID 추가

#       sheet.update_cell(row, 1, vid_url)
#       sheet.update_cell(row, 2, vid_title)
#       sheet.update_cell(row, 3, vid_length)
#       sheet.update_cell(row, 4, vid_date)
#       sheet.update_cell(row, 5, vid_views)
#       sheet.update_cell(row, 6, vid_id) 
#     else:
#       print(f"No video information found for ID {vid}.")
#   except Exception as e:
#     print(f"Error occurred for video ID {vid}: {e}")

#   row += 1

  ################################
from googleapiclient.discovery import build

def get_comments(video_id, api_key):
    try:
        youtube = build('youtube', 'v3', developerKey=api_key)
        comment_threads = youtube.commentThreads().list(
            part='snippet',
            videoId=video_id,
            maxResults=100
        ).execute()
        comments = [comment_thread['snippet']['topLevelComment']['snippet']['textDisplay']
                    for comment_thread in comment_threads.get('items', [])]
        return comments
    except Exception as e:
        print(f"Error occurred while getting comments for video ID {video_id}: {e}")
        return []

# api_key = "YOUR_API_KEY"
api_key = "AIzaSyCl2Ter4VgOR6X_QfLOSJF2ZVsNrlompow"

row = 1
for vid in video_ids:
    try:
        video = youtube.videos().list(part='snippet,contentDetails,statistics', id=vid).execute()
        if 'items' in video and video['items']:
            # vid_title = video['items'][0]['snippet']['title']
            vid_url = f"https://www.youtube.com/watch?v={vid}"
            # vid_length = video['items'][0]['contentDetails']['duration']
            # vid_date = video['items'][0]['snippet']['publishedAt']
            # vid_views = video['items'][0]['statistics']['viewCount']
            vid_id = vid
            comments = get_comments(vid, api_key)  # 댓글 가져오기

            sheet.update_cell(row, 1, vid_url)
            # sheet.update_cell(row, 2, vid_title)
            # sheet.update_cell(row, 3, vid_length)
            # sheet.update_cell(row, 4, vid_date)
            # sheet.update_cell(row, 5, vid_views)
            sheet.update_cell(row, 6, vid_id)
            sheet.update_cell(row, 7, "\n".join(comments))  # 댓글 열 추가
            time.sleep(0.5)
        else:
            print(f"No video information found for ID {vid}.")
    except Exception as e:
        print(f"Error occurred for video ID {vid}: {e}")
    row += 1
  
# # 재생목록에 비디오 추가
# playlist_id = 'https://youtube.com/playlist?list=PL_yXkA4LrwxKKswPTUlnk59UcoQS6GdtE&si=FTgMcF40Cmzf4wkq'

# for vid in video_ids:
#     youtube.playlistItems().insert(
#         part='snippet',
#         body={
#             'snippet': {
#                 'playlistId': playlist_id,
#                 'resourceId': {
#                     'kind': 'youtube#video',
#                     'videoId': vid
#                 }
#             }
#         }
#     ).execute()
# 재생목록에 비디오 추가
# playlist_id = 'PL_yXkA4LrwxKKswPTUlnk59UcoQS6GdtE&si=tY-qcmY2gqv2icjS'  # 여기에 재생목록의 ID를 입력하세요
# # https://youtube.com/playlist?list=PL_yXkA4LrwxKKswPTUlnk59UcoQS6GdtE&si=tY-qcmY2gqv2icjS
# # https://youtube.com/playlist?list=PL_yXkA4LrwxKKswPTUlnk59UcoQS6GdtE&si=9VKcOBD3wIk_tXzU
# for vid in video_ids:
#   try:
#     youtube.playlistItems().insert(part='snippet',
#                                    body={
#                                        'snippet': {
#                                            'playlistId': playlist_id,
#                                            'resourceId': {
#                                                'kind': 'youtube#video',
#                                                'videoId': vid
#                                            }
#                                        }
#                                    }).execute()
#   except Exception as e:
#     print(f"Error occurred while adding video {vid} to playlist: {e}")

  #############################3
# from googleapiclient.discovery import build

# def get_comments(video_id, api_key):
#     try:
#         # YouTube API 클라이언트 객체를 생성합니다.
#         youtube = build('youtube', 'v3', developerKey=api_key)

#         # 댓글 스레드 목록을 요청합니다.
#         comment_threads = youtube.commentThreads().list(
#             part='snippet',
#             videoId=video_id,
#             maxResults=100  # 최대 100개의 댓글을 가져옵니다.
#         ).execute()

#         # 댓글 텍스트를 추출하여 리스트로 반환합니다.
#         comments = [comment_thread['snippet']['topLevelComment']['snippet']['textDisplay']
#                     for comment_thread in comment_threads.get('items', [])]

#         return comments

#     except Exception as e:
#         print(f"Error occurred while getting comments for video ID {video_id}: {e}")
#         return []

# # 사용 예시
# video_id = "nJnhBBxhzZE"
# api_key = "AIzaSyCl2Ter4VgOR6X_QfLOSJF2ZVsNrlompow"

# comments = get_comments(video_id, api_key)
# print("Comments:", comments)