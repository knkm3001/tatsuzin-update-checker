import re
import json
import requests
import feedparser
import traceback
import sqlite3
from sqlite3 import IntegrityError
from bs4 import BeautifulSoup
import env

DB_NAME = '/home/db_data/Tatsuzin.articles'
TATSUZIN_INFO_URL = 'https://www.tatsuzin.info/rss/'
SLACK_WEB_HOOK_URL = env.SLACK_WEB_HOOK_URL

def set_logger():
    logger = getLogger(__name__)

    log_format = Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s", "%Y-%m-%dT%H:%M:%S")

    stream_handler = StreamHandler()
    stream_handler.setLevel(INFO)
    stream_handler.setFormatter(log_format)
    logger.addHandler(stream_handler)

    log_file = "tatsuzin_update_checker.log"

    file_handler = FileHandler(filename=log_file, encoding='utf-8')
    file_handler.setLevel(INFO)
    file_handler.setFormatter(log_format)
    logger.addHandler(file_handler)

    logger.setLevel(INFO)
    logger.propagate = False
    return logger

def main():
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row 
        cur = conn.cursor()
        create_table(cur,conn)
        lateste_url = fetch_latest_record(cur,conn)
        for entry in feedparser.parse(TATSUZIN_INFO_URL).entries:
            if(re.search(r'.+の達人.+公開のお知らせ',entry.title)):
                if(lateste_url == entry.link):
                    logger.info('更新情報はないのでおしまい\n')
                    break
                title = re.sub(r'[「|」]','',entry.title)
                html = requests.get(entry.link).content
                soup = BeautifulSoup(html, 'lxml')
                contents = soup.select('#Contents_main> p:nth-child(4)')
                m = re.search(r'公開プログラムバージョン.+?(データベース.+?。)',str(contents[0]))
                if  m:
                    tmp = re.sub(r'<.+?>','__',m.group())
                    version_info = re.sub(r'(__)+','\n',tmp)
                    values = [title,version_info,entry.link,entry.updated]
                    insert_update_info(cur,conn,values)
                    logger.info("New info: "+title+version_info)
                    slack_notify(entry.link,title,version_info)
    except:
        traceback.print_exc()
    finally:
        cur.close()
        conn.close()

def insert_update_info(cur,conn,values):
    try:
        cur.execute(
            "INSERT INTO articles(title,version_info,url,publication_date) values(?,?,?,?)",
            values
        )
        conn.commit()
    except IntegrityError:
        print('IntegrityError!')
        pass

def create_table(cur,conn):
    cur.execute(
        """
            CREATE TABLE IF NOT EXISTS articles(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title String,
                version_info String,
                url String UNIQUE,  
                publication_date DATETIME
            )
        """
        )
    conn.commit()

def fetch_latest_record(cur,conn):
    cur.execute(
        """
            select * from articles order by publication_date DESC limit 1
        """
        )
    row = cur.fetchone()
    return row['url'] if row else None

def slack_notify(url,title,update_info):
    payload = json.dumps({
        "text": """
                達人シリーズのバージョンアップデート情報が公開されました。\nサーバのアップデートが完了するまで、PCでのアップデートはお控えください。\n<{0}|{1}>
                """.format(url,title),
        "attachments": [{
            "text": update_info
        }]
    })
    requests.post(SLACK_WEB_HOOK_URL, payload)

if __name__=='__main__':
    main()
