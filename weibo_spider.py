import datetime
from posixpath import basename, split
from bs4 import BeautifulSoup
import os
import requests
import urllib.request

# 测试函数
class TestFunc(object):
    def __init__(self) -> None:
        pass

    def testNetworkV1(self):
        url = "https://wx4.sinaimg.cn/mw2000/008l2znhgy1h1t7gxf392j32c0340hdt.jpg"    
        request = urllib.request.Request(url)
        response = urllib.request.urlopen(request)
        img_name = basename(url)
        if (response.getcode() == 200):
            with open(img_name, "wb") as f:
                f.write(response.read())

    # 测试函数
    def testNetworkV2(self):
        url = "https://wx4.sinaimg.cn/mw2000/008l2znhgy1h1t7gxf392j32c0340hdt.jpg"    
        img_name = basename(url)
        urllib.request.urlretrieve(url, img_name)

    # 解析url参数  
    def testParseUrl(self):
        url = "https://weibo.com/ajax/statuses/buildComments?is_reload=1&id=4764434713804942&is_show_bulletin=2&is_mix=0&count=20&type=feed&uid=7743679062"
        result = urllib.parse.urlsplit(url)
        query = dict(urllib.parse.parse_qsl(result.query))
        print(query)

# 获取uid所有的blog
class BlogSpider(object):
    def __init__(self, uid):
        self.comment_spider = CommentSpider()
        with open("./history.txt", "r") as file:
            self.download_history = file.read().splitlines()
        self.history_file = open("./history.txt", "a")
        self.getAllBlog(uid)

    # 获取uid全部微博
    def getAllBlog(self, uid):
        page = 1
        since_id = 0
        print("开始获取 uid={} 的评论图".format(uid))
        while(True):
            print("# page={}, sinceId = {}".format(page, since_id))
            raw_data = self.getBlogWorkflow(uid, page, since_id)
            since_id = self.getSinceId(uid, raw_data)
            page += 1
            if page > 1: # 最多看1页，20条微博
                break
            if since_id == "":
                break 

    # loadmore的实现逻辑
    def getBlogWorkflow(self, uid, page, since_id):
        url = "https://weibo.com/ajax/statuses/mymblog"
        headers = {
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36 Edg/92.0.902.55",
            # cookie是会变的，通过抓包，替换为你自己最新的
            "cookie":"xxxxxx",
        }
        params = {
            "uid" : uid,
            "page" : page,
            "since_id":since_id,
            "feature":0
        }
        r = requests.get(url, headers = headers, params = params)
        if r.status_code == 200:
            return r.json()
        else:
            return None

    # 获取一次loadmore的since_id，并记录
    def getSinceId(self, uid, raw_data):
        blogs = raw_data["data"]["list"]
        since_id = raw_data["data"]["since_id"]
        for blog in blogs:
            bid = blog["id"]
            pidstr = blog["idstr"]
            text = blog["text"]
            if pidstr in self.download_history:
                print("## 已经下载过 bid={} 的评论图".format(bid))
                continue
            print("## 开始获取 uid={}  bid={} 的评论图".format(uid, bid))
            self.download_history.append(bid)
            self.history_file.write("{}\n".format(bid))
            self.comment_spider.getBlogImage(blog)
            self.comment_spider.getAllComment(uid, bid)
        return since_id

     
# 创建一个class用于获取一条blog下所有评论图，blog标识定为bid
class CommentSpider(object):
    def __init__(self) -> None:
        self.image_url_array = []
    # 获取当前blog本身携带的图片
    def getBlogImage(self, raw_data):
        if "pic_infos" in raw_data and "pic_ids" in raw_data:
            pic_ids = raw_data["pic_ids"]
            pic_infos = raw_data["pic_infos"]
            for single_id in pic_ids:
                real_url = pic_infos[single_id]["original"]["url"]
                if real_url not in self.image_url_array:
                    self.image_url_array.append(real_url)
    
    # 根据bid，获取当前blog评论区中所有的图片
    def getAllComment(self, uid, bid):
        # 第一次请求时 max_id=0，后续的max_id都是从前一次请求中获取
        max_id = 0
        while(True):
            # print("#### max_id:", max_id)
            raw_data = self.getCommentWorkflow(uid, bid, max_id, False)
            if raw_data != None:
                max_id = self.getCommentImage(raw_data)
                if max_id == 0:
                    break
            else:
                print("#### 异常:", raw_data)
                break
        print("### 图片个数:", len(self.image_url_array))
        for item in self.image_url_array:
            self.download(item)

    # 根据bid，max_id，发出一次请求
    def getCommentWorkflow(self, uid, bid, max_id, is_sub):
        url = "https://weibo.com/ajax/statuses/buildComments"
        headers = {
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36 Edg/92.0.902.55",
        }
        params = {
            "flow" : 0,
            "is_reload" : 1,
            "id" : bid,
            "is_show_bulletin" : 2,
            "is_mix" : 0,
            "max_id" : max_id,
            "count" : 20,
            "uid" : uid
        }
        if is_sub == True:
            params["flow"] = 1
            params["is_mix"] = 1
            params["fetch_level"] = 1
        r = requests.get(url, headers= headers, params=params)
        if r.status_code == 200:
            return r.json()
        else:
            return None
    
    # 解析评论区，获取本次请求中获取的评论图片
    def getCommentImage(self, raw_data):
        data = raw_data["data"]
        max_id = raw_data["max_id"]
        for item in data:
            content = BeautifulSoup(item["text"], "html.parser").text
            # 评论者 id，name，city
            user = item["user"]
            sub_uid = user["id"]
            if "url_struct" in item:
                url_struct = item["url_struct"]
                for single in url_struct:
                    if "pic_infos" in single and "pic_ids" in single:
                        pic_ids = single["pic_ids"]
                        pic_infos = single["pic_infos"]
                        for single_id in pic_ids:
                            real_url = pic_infos[single_id]["woriginal"]["url"]
                            if real_url not in self.image_url_array:
                                self.image_url_array.append(real_url)
                                # print("##### ", real_url)

            if "comments" in item:
                sub_bid = item["id"]
                sub_max_id = 0
                # sub_comments = item["comments"]  不用取出来，重新请求
                # print("找到子评论")
                while(True):
                    html = self.getCommentWorkflow(sub_bid, sub_uid, sub_max_id, True)
                    if html != None:
                        index2 = 0
                        sub_max_id = self.getCommentImage(html)
                        # max_id 为 0 时，表示爬取结束
                        if sub_max_id == 0:
                            break
        return max_id

    def download(self, url):
        file_name = "./weibo_image/"+basename(url)
        # 已经下载的文件跳过
        if os.path.exists(file_name):
            # print("#### "+ file_name + "已存在。")
            pass
        else:
            urllib.request.urlretrieve(url, file_name)
            print("#### "+ file_name + "下载完成。")  

if __name__ == "__main__":
    start_time = datetime.datetime.now()
    BlogSpider(00000000000) #这里替换为目标用户uid
    end_time = datetime.datetime.now()
    print("completion, spend time :", end_time - start_time)
    # 考虑多线程