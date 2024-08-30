import csv,time,random,requests,re
from bs4 import BeautifulSoup
from urllib.parse import urlencode
import pandas as pd
from pyecharts.charts import Pie,Line,Bar,Radar,Grid,Page
from pyecharts import options as opts

# names是唯一需要修改的部分，只需要把你需要获得信息的微博用户的微博昵称加引号完整写入列表中即可
# 注意不能有空格，不能有缺省，昵称是确认信息采集正确的唯一依据
names=['TOP登陆少年-朱志鑫', 'TOP登陆少年-苏新皓', 'TOP登陆少年-张极','TOP登陆少年-左航','TOP登陆少年-张泽禹']

#以下不需要修改
member_number=len(names)
members=[f'https://m.weibo.cn/n/{name}'for name in names]
headers = {
    'Accept': 'application/json, text/plain, */*',
    'Mweibo-Pwa': '1',
    'Referer': 'https://m.weibo.cn/',
    'Sec-Ch-Ua': '"Microsoft Edge";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
    'Sec-Ch-Ua-Mobile': '?0',
    'Sec-Ch-Ua-Platform': '"Windows"',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0',
    'X-Requested-With': 'XMLHttpRequest',
    'X-Xsrf-Token': 'f2d20b'
}


for i in range(len(names)):
    csvfile = open(f'{names[i]}_WeiboData.csv', 'wt+', encoding='utf-8-sig', newline='')
    # csvfile=open(f'{names[i]}_comment.csv','wt+',encoding='utf-8-sig',newline='')
    writer = csv.writer(csvfile)

    # text_string, at_list, topic_list, icon_List, super_list,location_list, photo_list, other_link_list
    writer.writerow(['id','mid','weibo_created_at','source','region','is_edited','reposts','comments','attitudes','weibo_text','ats','topics','icons','supers','locations','photos','other_links'])

    # 每一个value（用户Id)会有对应的特定的containerid，这个containerid也需要获取
    # 由于需要爬取多个成员的containerid,一个一个打开对应的页面过于耗时，绞尽脑汁想出来获取containerid的另一种方式
    # 通过模拟实际打开页面的request方式，获得containerid
    response = requests.get(url='https://m.weibo.cn/', headers=headers)
    time.sleep(2)
    response = requests.get(url=members[i], headers=headers)

    # 获得的members是一个中文的链接，譬如“n/时代少年团队长-马嘉祺",需要转化为数字id
    url = str(response.url)
    url = re.match('https://m.weibo.cn/u/(\d*)', url)
    try:
        value = url.group(1)
    except AttributeError:
        print(url)

    response = requests.get(url='https://m.weibo.cn/api/config', headers=headers)
    response = requests.get('https://m.weibo.cn/api/container/getIndex?type=uid&value={}'.format(value),
                            headers=headers)
    if response.status_code == 200:
        json = response.json()

    # 这里对应有若干个containerid,分别对应的是profile,weibo,video,super和album对应的container
    # 我们需要爬取的是weibo对应的containerid
    containerid = json['data']['tabsInfo']['tabs'][1]['containerid']
    params = {
        'type': 'uid',
        'value': value,
        'containerid': containerid
    }

    # 初始化
    page_base_url = 'https://m.weibo.cn/api/container/getIndex?'
    comment_base_url = 'https://m.weibo.cn/comments/hotflow?'
    extend_base_url = 'https://m.weibo.cn/statuses/extend?'
    since_ids = [0]
    errorlist = []


    # 基于当前的since_id，获取更多的since_id和当前since_id对应的微博的id和mid
    def get_page(since_id):
        if since_id != 0:
            params['since_id'] = since_id
        url = page_base_url + urlencode(params)
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                json = response.json()
                if json['ok'] == 0:
                    print(url)
                    # 设置循环等待，直到成功采集到，以保证采集数据的连贯性
                    retry = 0
                    while (json['ok'] == 0 and retry <= 3):
                        # 重新模拟一次访问主页的过程
                        time.sleep(random.randint(5, 10))
                        response = requests.get(url=members[i], headers=headers)
                        response = requests.get(url='https://m.weibo.cn/api/config', headers=headers)
                        response = requests.get(
                            url='https://m.weibo.cn/api/container/getIndex?type=uid&value={}'.format(value),
                            headers=headers)
                        response = requests.get(url=url, headers=headers)
                        json = response.json()
                        retry += 1
                        # if retry==3:
                        #     retry = input('输入retry，如果retry=0则继续尝试')
                        #     retry = int(retry)
                if json['ok'] == 1:
                    since_ids.append(json['data']['cardlistInfo']['since_id'])
                    for weibo_json in json['data']['cards']:
                        yield weibo_json
                else:
                    errorlist.append(f'"ok”=0 when getting page {url}')
        except KeyError as e:
            errorlist.append(f'{e} when getting page {url}')

    # 获取并解析extend内容
    def get_parse_extend(id):
        url = extend_base_url + urlencode({'id': id})
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            json = response.json()
            if json['ok'] == 0:
                print(url)

            if json['ok'] == 1:
                text = json['data']['longTextContent']
                parsed_text = parse_text(text)
                # print('parse_text',len(parsed_text),type(parsed_text),parsed_text)
            else:
                parsed_text = ["cannot get text", "cannot get text", "cannot get text", "cannot get text",
                               "cannot get text", "cannot get text", "cannot get text", "cannot get text"]
            # 如果是转发内容，则会在extend的部分显示retweeted_status，否则字典中没有这个key
            try:
                repost_text = json['data']['retweet_count']
                parsed_repost_text = parse_text(repost_text)
            except KeyError as e:
                # do nothing
                parsed_repost_text = None

            return parsed_text, parsed_repost_text


    # 解析微博文本
    # 目前还缺少
    # emoji的分离
    # //转发内容
    # return的依次是text_string, at_list, topic_list, icon_List, super_list,location_list, photo_list, other_link_list
    def parse_text(text):
        newrow = []
        text = BeautifulSoup(text, 'lxml')
        # 拆分处文本数据
        newrow.append(text.text)

        # 查找@，一部分微博没有@
        ats = text.find_all('a', href=re.compile('/n/\w+'))
        ats = [at.text for at in ats]
        newrow.append(ats)
        # except:
        #     newrow.append('no@')

        # 查找微博话题，一部分微博没有话题
        topics = text.find_all('a', href=re.compile('https://m.weibo.cn/search\?\w+'))
        topics = [topic.text for topic in topics]
        newrow.append(topics)
        # except:
        # newrow.append('no#')

        # 查找是否有微博表情，一部分微博没有表情
        # 其中，同时查找超话和地点
        icons = text.find_all('img')
        alts = []
        supers = []
        locations = []
        photos = []
        for icon in icons:
            try:
                alts.append(icon['alt'])

            # KeyError的原因即是因为没有alt这个attribute，即不是表情
            except KeyError:
                # 分别对应的是微博链接、微博视频、微博超话、查看图片、地点
                # 之所以使用正则表达式匹配是因为我一部分链接使用的是不含https的链接文本，另一部分使用含有https的连接文本
                if re.search("timeline_card_small_web_default.png", icon['src']) is not None or re.search(
                    "timeline_card_small_video_default.png", icon['src']) is not None:
                    continue
                # 添加超话
                elif re.search("timeline_card_small_super_default.png", icon['src']) is not None:
                    supers.append(icon.find_parent('span').nextSibling.text)
                # 添加地点
                elif re.search("timeline_card_small_location_default.png", icon['src']) is not None:
                    locations.append(icon.find_parent('span').nextSibling.text)
                # 添加查看图片计数器
                elif re.search("timeline_card_small_photo_default.png", icon['src']) is not None:
                    photos.append(icon.find_parent('span').nextSibling.text)
                # else:
                    # print(f'error while dealing with {icon["src"]}')
        newrow.extend([alts, supers, locations, photos])
        # except:
        #     newrow.append('noicon')

        # 查找是否有其他微博链接
        other_links = text.find_all('a', href=re.compile('https://weibo.cn/sinaurl\?\w+'))
        other_links = [other_link.text for other_link in other_links]
        newrow.append(other_links)

        # 查找是否有有微博视频
        # surls =text.find_all('a',href=re.compile('https://video.weibo.com/show\?\w+'))
        # for surl in surls:

        # except:
        #     newrow.append('nourl')

        # newrow_list依次是text_string, at_list, topic_list, icon_List, super_list,location_list, photo_list, other_link_list
        return newrow


    def parse_weibo(weibo_json, is_repost):

        # 使用parse_weibo函数同时解析原微博和转发微博,用is_repost判别
        if is_repost == False:
            mblog = weibo_json['mblog']
        else:
            mblog = weibo_json

        id = mblog['id']
        mid = mblog['mid']
        created_at = mblog['created_at']
        source = mblog['source']
        try:
            region = mblog['region_name']
        except KeyError:
            region = ''
            # print(id)
        is_edited = mblog['edit_config']['edited']
        reposts_count = mblog['reposts_count']
        comments_count = mblog['comments_count']
        attitudes_count = mblog['attitudes_count']
        basic_info = [id, mid, created_at, source, region, is_edited, reposts_count, comments_count, attitudes_count]

        # 一部分微博内容需要展开全文
        is_longtext = mblog['isLongText']
        if is_longtext == 'true':
            parsed_text, parsed_repost_text = get_parse_extend(id)
        else:
            parsed_text = parse_text(mblog['text'])
        if is_repost == False:
            basic_info.extend(parsed_text)
        else:
            basic_info.extend(parsed_repost_text)

        return basic_info, id, mid

    # 核心循环程序，count用于计算跑了多少
    count = 0
    while since_ids:
        since_id = since_ids.pop(0)
        for weibo_json in get_page(since_id):
            newrow = []
            # card_type=9的是微博内容卡片
            card_type = weibo_json['card_type']
            if card_type == 9:
                is_repost = False
                parsed_weibo, id, mid = parse_weibo(weibo_json, is_repost)
                # print('main',len(parsed_weibo),type(parsed_weibo),parsed_weibo)
                newrow.extend(parsed_weibo)
                writer.writerow(newrow)

        print(count, end=' ')
        count += 1

    csvfile.close()
    #
    print(names[i], errorlist)

# 为所有成员的数据面板记录max数据
max_month = 0
max_dayname = 0
max_clock = 9
max_number_month = 0
max_number_dayname = 0
max_number_clock = 0


def change_max(type, isnumber, value_):
    global max_month, max_dayname, max_clock, max_number_month, max_number_dayname, max_number_clock
    if type == 'month':
        if isnumber:
            max_number_month = value_
        else:
            max_month = value_
    elif type == 'dayname':
        if isnumber:
            max_number_dayname = value_
        else:
            max_dayname = value_
    elif type == 'clock':
        if isnumber:
            max_number_clock = value_
        else:
            max_clock = value_
    else:
        print(f"change_max_error of {type} when value is {value_}")


#单个成员面板
for member_index in range(member_number):

    # print(names[member_index])
    df = pd.read_csv(names[member_index] + '_WeiboData.csv')
    # print(df.info())

    # 对于日期数据进行清洗
    df['time'] = pd.to_datetime(df['weibo_created_at'], format="%a %b %d %H:%M:%S %z %Y")

    # 按照发博的星期分组
    df_dayname = df[['reposts', 'comments', 'attitudes']].groupby(df['time'].dt.day_name()).mean()
    df_dayname['number'] = df.groupby(df['time'].dt.day_name()).size()
    daynames = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    df_dayname = df_dayname.reindex(daynames)
    # print(df_dayname)

    # 按照发博的时间段分组
    df['precise_time'] = df['time'].dt.hour.astype('str') + ":" + df['time'].dt.minute.astype('str') + ":" + df[
        'time'].dt.second.astype('str')
    df_clock = df[['reposts', 'comments', 'attitudes']].groupby(
        pd.to_datetime(df['precise_time'], format="%H:%M:%S").dt.hour).mean()
    df_clock['number'] = df.groupby(pd.to_datetime(df['precise_time'], format="%H:%M:%S").dt.hour).size()
    for i in range(0, 24):
        if i not in df_clock.index:
            df_clock.loc[i, 'number'] = 0
    df_clock = df_clock.sort_index(ascending=True)
    # 设置一个反向时间索引的dataframe是因为Radar参数is_clockwise似乎不起作用
    # adverse_clocks=[0,23,22,21,20,19,18,17,16,15,14,13,12,11,10,9,8,7,6,5,4,3,2,1]
    df_adverse_clock = df_clock.sort_index(ascending=False)
    # print(df_clock)

    # 设置一个过少的区间，为之后的饼图做铺垫
    df_clock_samples = df_clock['number'].sum()
    df_clock_samples_criteria = df_clock_samples * 0.01
    df_clock_small_sample_mask = df_clock['number'] < df_clock_samples_criteria
    # print(df_clock_small_sample_mask.info())

    # 按照发播的时间宽度切割分组，但是也可以改成10D,20D这样的区间
    df.set_index('time', inplace=True)
    df_month = df[['reposts', 'comments', 'attitudes']].resample('M').mean()
    df_month['number'] = df.resample('M').size()

    member_grid = Page(page_title=names[member_index], layout=Page.SimplePageLayout)

    member_grid_month = Grid()
    member_grid_dayname = Grid()
    member_grid_clock = Grid()

    for type in ['month', 'dayname', 'clock']:
        member_line = Line()

        # 这里关于interval的设置主要是为了对齐坐标轴
        interval = 20
        max_index = 0
        for bottom_index in ['reposts', 'comments', 'attitudes']:

            if eval('df_' + type)[bottom_index].max() > max_index:
                max_index = eval('df_' + type)[bottom_index].max()
            member_line.add_xaxis(eval('df_' + type).index.tolist())
            member_line.add_yaxis(bottom_index, eval('df_' + type)[bottom_index].tolist(),
                                  label_opts=opts.LabelOpts(is_show=False))

        if eval('max_' + type) < max_index: change_max(type, False, max_index)

        # 这里关于axis的max_的设置主要是用于对其坐标轴网格
        member_line.set_global_opts(legend_opts=opts.LegendOpts(pos_left="72%"),
                                    xaxis_opts=opts.AxisOpts(is_show=False),
                                    yaxis_opts=opts.AxisOpts(interval=int(max_index / (interval) / 1000) * 1000,
                                                             max_=int(max_index / interval / 1000) * (
                                                                         1 + interval) * 1000))

        max_index = eval('df_' + type)['number'].max()
        if eval('max_number_' + type) < max_index: change_max(type, True, max_index)
        member_bar = (Bar()
                      .add_xaxis(eval('df_' + type).index.tolist())
                      .add_yaxis("numbers", eval('df_' + type)['number'].tolist(),
                                 label_opts=opts.LabelOpts(is_show=False),
                                 itemstyle_opts=opts.ItemStyleOpts(opacity=0.5))
                      .set_global_opts(
            title_opts=opts.TitleOpts(title=f"Basic Weibo Indices of {names[member_index]} by {type.capitalize()}",
                                      pos_top="2%"),
            legend_opts=opts.LegendOpts(pos_left="82%", pos_top="4.5%"),
            yaxis_opts=opts.AxisOpts(position="right", interval=int(max_index / (interval)) * 3,
                                     max_=int(max_index / interval) * (1 + interval) * 3)))

        (eval("member_grid_" + type).add(chart=member_bar,
                                         grid_opts=opts.GridOpts(pos_left="10%", pos_right="5%", pos_top="10%",
                                                                 pos_bottom="5%"), ))
        (eval("member_grid_" + type).add(chart=member_line,
                                         grid_opts=opts.GridOpts(pos_left="10%", pos_right="5%", pos_top="10%",
                                                                 pos_bottom="5%"), ))
        member_line.set_global_opts(title_opts=opts.TitleOpts(title=""))
        # eval("member_grid_"+type).render(names[member_index]+'_grid'+"_"+type+'.html')
        member_grid.add(eval("member_grid_" + type))

    member_clock_pie = (Pie()
                        .add("sample size too small",
                             [(x, y) for x, y in zip(df_clock_small_sample_mask.index, df_clock_small_sample_mask)],
                             rosetype="area",
                             start_angle=-262.5, is_avoid_label_overlap=False,
                             color="rgb(0,0,0)", color_by="series",
                             label_line_opts=opts.PieLabelLineOpts(is_show=False),
                             radius=["5%", "80%"],
                             label_opts=opts.LabelOpts(is_show=False),
                             itemstyle_opts=opts.ItemStyleOpts(opacity=0.2))
                        .add("time", [(x, y) for x, y in zip(df_clock.index, df_clock['number'])], rosetype="area",
                             start_angle=-262.5, is_avoid_label_overlap=False, color_by="series",
                             label_line_opts=opts.PieLabelLineOpts(is_show=False),
                             radius=["5%", "80%"],
                             label_opts=opts.LabelOpts(is_show=False),
                             itemstyle_opts=opts.ItemStyleOpts(opacity=0.8)
                             )
                        .set_global_opts(legend_opts=opts.LegendOpts(is_show=True))
                        )
    # member_clock_pie.render('pie.html')

    member_clock_radar = Radar()
    member_clock_radar.add_schema(schema=[{"name": str(clock_) + ":00"} for clock_ in df_adverse_clock.index],
                                  shape="circle", start_angle=105, radius=["30%", "80%"],
                                  angleaxis_opts=opts.AngleAxisOpts(),
                                  radiusaxis_opts=opts.RadiusAxisOpts(),
                                  polar_opts=opts.PolarOpts()
                                  )
    for bottom_index in ['reposts', 'comments', 'attitudes']:
        member_clock_radar.add(bottom_index, [{"value": df_adverse_clock[bottom_index].tolist(), "name": bottom_index}],
                               label_opts=opts.LabelOpts(is_show=False))
    # member_clock_radar.render('radar.html')

    member_grid_polar = Grid()
    member_grid_polar.add(chart=member_clock_radar,
                          grid_opts=opts.GridOpts(pos_left="10%", pos_right="5%", pos_top="10%", pos_bottom="5%"))
    member_grid_polar.add(chart=member_clock_pie,
                          grid_opts=opts.GridOpts(pos_left="10%", pos_right="5%", pos_top="10%", pos_bottom="5%"))
    # member_grid_polar.render(names[member_index]+'clock_grid.html')

    member_grid.add(member_grid_polar)
    member_grid.render(names[member_index] + '_member_grid.html')

line_reposts = (Line())
line_comments = (Line())
line_attitudes = (Line())


def func(line_name, name, x, y):
    line_name.add_xaxis(x)
    line_name.add_yaxis(name, y)


basic_indices_page_vertical = Grid(init_opts=opts.InitOpts(width=f'{800 * member_number}px', height='1440px'))
basic_indices_page_polar = Grid(init_opts=opts.InitOpts(width=f'{800 * member_number}px', height='600px'))
basic_indices_page_bottom = Grid(init_opts=opts.InitOpts(width=f'{800 * member_number}px', height='540px'))
basic_indices_page = Page()
basic_indices_blank_title = (
    Line(init_opts=opts.InitOpts(width=f'{800 * member_number}px', height='30px')).set_global_opts(
        title_opts=opts.TitleOpts(title="Basic Weibo Indices Panel",
                                  title_textstyle_opts=opts.TextStyleOpts(font_size=30), pos_left='center')))
basic_indices_page.add(basic_indices_blank_title)

#整个数据面板
for member_index in range(member_number):

    # print(names[member_index])
    df = pd.read_csv(names[member_index] + '_WeiboData.csv')
    # print(df.info())

    # 对于日期数据进行清洗
    df['time'] = pd.to_datetime(df['weibo_created_at'], format="%a %b %d %H:%M:%S %z %Y")

    # 按照发博的星期分组
    df_dayname = df[['reposts', 'comments', 'attitudes']].groupby(df['time'].dt.day_name()).mean()
    df_dayname['number'] = df.groupby(df['time'].dt.day_name()).size()
    daynames = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    df_dayname = df_dayname.reindex(daynames)
    # print(df_dayname)

    # 按照发博的时间段分组
    df['precise_time'] = df['time'].dt.hour.astype('str') + ":" + df['time'].dt.minute.astype('str') + ":" + df[
        'time'].dt.second.astype('str')
    df_clock = df[['reposts', 'comments', 'attitudes']].groupby(
        pd.to_datetime(df['precise_time'], format="%H:%M:%S").dt.hour).mean()
    df_clock['number'] = df.groupby(pd.to_datetime(df['precise_time'], format="%H:%M:%S").dt.hour).size()
    for i in range(0, 24):
        if i not in df_clock.index:
            df_clock.loc[i, 'number'] = 0
    df_clock = df_clock.sort_index(ascending=True)
    # 设置一个反向时间索引的dataframe是因为Radar参数is_clockwise似乎不起作用
    # adverse_clocks=[0,23,22,21,20,19,18,17,16,15,14,13,12,11,10,9,8,7,6,5,4,3,2,1]
    df_adverse_clock = df_clock.sort_index(ascending=False)
    # print(df_clock)

    # 设置一个过少的区间，为之后的饼图做铺垫
    df_clock_samples = df_clock['number'].sum()
    df_clock_samples_criteria = df_clock_samples * 0.01
    df_clock_small_sample_mask = df_clock['number'] < df_clock_samples_criteria
    # print(df_clock_small_sample_mask.info())

    # 按照发播的时间宽度切割分组，但是也可以改成10D,20D这样的区间
    df.set_index('time', inplace=True)
    df_month = df[['reposts', 'comments', 'attitudes']].resample('M').mean()
    df_month['number'] = df.resample('M').size()

    # member_grid=Page(page_title=names[member_index],layout=Page.SimplePageLayout)

    member_grid_month = Grid()
    member_grid_dayname = Grid()
    member_grid_clock = Grid()
    location_count = 0
    for type in ['month', 'dayname', 'clock']:

        member_line = Line()

        # 这里关于interval的设置主要是为了对齐坐标轴
        interval = 20
        max_index = 0
        for bottom_index in ['reposts', 'comments', 'attitudes']:
            member_line.add_xaxis(eval('df_' + type).index.tolist())
            member_line.add_yaxis(bottom_index, eval('df_' + type)[bottom_index].tolist(),
                                  label_opts=opts.LabelOpts(is_show=False))

        pos_left = 75 + 800 * member_index
        pos_right = 800 * member_number - (800 * (member_index + 1) - 50)
        pos_top = 5 + 2 + 32 * location_count
        pos_bottom = 100 - (5 + 30 - 2 + 32 * location_count)

        # 这里关于axis的max_的设置主要是用于对其坐标轴网格
        member_line.set_global_opts(xaxis_opts=opts.AxisOpts(is_show=False), yaxis_opts=opts.AxisOpts(
            interval=int(eval("max_" + type) / (interval) / 1000) * 1000,
            max_=int(eval("max_" + type) / interval / 1000) * (1 + interval) * 1000),
                                    legend_opts=opts.LegendOpts(pos_left=f"{400 * member_number - 175}px",
                                                                pos_top="0%"),
                                    title_opts=opts.TitleOpts(title=names[member_index], pos_left=f"{pos_left}px",
                                                              pos_top="2%")
                                    )

        member_bar = (Bar()
                      .add_xaxis(eval('df_' + type).index.tolist())
                      .add_yaxis("numbers", eval('df_' + type)['number'].tolist(),
                                 label_opts=opts.LabelOpts(is_show=False),
                                 itemstyle_opts=opts.ItemStyleOpts(opacity=0.5))
                      .set_global_opts(
            title_opts=opts.TitleOpts(title=f"By {type.capitalize()}", pos_left=f"center", pos_top=f"{pos_top - 2}%"),
            legend_opts=opts.LegendOpts(pos_left=f"{400 * member_number + 100}px", pos_top="0%"),
            yaxis_opts=opts.AxisOpts(position="right", interval=int(eval("max_number_" + type) / (interval)) * 2,
                                     max_=int(eval("max_number_" + type) / interval) * (1 + interval) * 2)))

        # (eval("member_grid_"+type).add(chart=member_bar, grid_opts=opts.GridOpts(pos_left="10%", pos_right="5%", pos_top="10%", pos_bottom="5%"),))
        # (eval("member_grid_"+type).add(chart=member_line, grid_opts=opts.GridOpts(pos_left="10%", pos_right="5%", pos_top="10%", pos_bottom="5%"),))
        # member_grid.add(eval("member_grid_"+type))
        # eval("member_grid_"+type).render(names[member_index]+'_grid'+"_"+type+'.html')

        # print(pos_left,pos_right,pos_top,pos_bottom)
        basic_indices_page_vertical.add(chart=member_bar,
                                        grid_opts=opts.GridOpts(pos_left=f"{pos_left}px", pos_right=f"{pos_right}px",
                                                                pos_top=f"{pos_top}%", pos_bottom=f"{pos_bottom}%"))
        basic_indices_page_vertical.add(chart=member_line,
                                        grid_opts=opts.GridOpts(pos_left=f"{pos_left}px", pos_right=f"{pos_right}px",
                                                                pos_top=f"{pos_top}%", pos_bottom=f"{pos_bottom}%"))
        location_count = location_count + 1

    # basic_indices_page_vertical.render('basic_indices_page_vertical.html')

    center_position = [f'{412.5 + member_index * 800}px', "50%"]
    # radius_set=["30%","90%"]
    member_clock_pie = (Pie()
                        .add("sample size too small",
                             [(x, y) for x, y in zip(df_clock_small_sample_mask.index, df_clock_small_sample_mask)],
                             rosetype="area",
                             start_angle=-262.5, is_avoid_label_overlap=False,
                             color="rgb(0,0,0)", color_by="series",
                             label_line_opts=opts.PieLabelLineOpts(is_show=False),
                             radius=["5%", "90%"],
                             label_opts=opts.LabelOpts(is_show=False),
                             itemstyle_opts=opts.ItemStyleOpts(opacity=0.2),
                             center=center_position)
                        .add("time", [(x, y) for x, y in zip(df_clock.index, df_clock['number'])], rosetype="area",
                             start_angle=-262.5, is_avoid_label_overlap=False,
                             color_by="series",
                             label_line_opts=opts.PieLabelLineOpts(is_show=False),
                             radius=["5%", "90%"],
                             label_opts=opts.LabelOpts(is_show=False),
                             itemstyle_opts=opts.ItemStyleOpts(opacity=0.8),
                             center=center_position
                             )
                        # .set_global_opts(title_opts=opts.TitleOpts(subtitle="The "))
                        )
    # member_clock_pie.render('pie.html')

    member_clock_radar = Radar()
    member_clock_radar.add_schema(schema=[{"name": str(clock_) + ":00"} for clock_ in df_adverse_clock.index],
                                  shape="circle", start_angle=105, radius=["30%", "90%"],
                                  # angleaxis_opts=opts.AngleAxisOpts(),
                                  # radiusaxis_opts=opts.RadiusAxisOpts(),
                                  # polar_opts=opts.PolarOpts(),
                                  center=center_position
                                  )
    for bottom_index in ['reposts', 'comments', 'attitudes']:
        member_clock_radar.add(bottom_index, [{"value": df_adverse_clock[bottom_index].tolist(), "name": bottom_index}],
                               label_opts=opts.LabelOpts(is_show=False), radar_index=member_index)

    # 避免出现红色
    # member_clock_radar.add('blank1',[])
    # member_clock_radar.add('blank2',[])
    # member_clock_radar.add('blank3',[])

    member_clock_radar.set_global_opts(legend_opts=opts.LegendOpts(is_show=False))
    # member_clock_radar.render(names[member_index]+'radar.html')

    # member_grid_polar=Grid()
    # member_grid_polar.add(chart=member_clock_radar,grid_opts=opts.GridOpts(pos_left="10%", pos_right="5%", pos_top="10%", pos_bottom="5%"))
    # member_grid_polar.add(chart=member_clock_pie,grid_opts=opts.GridOpts(pos_left="10%", pos_right="5%", pos_top="10%", pos_bottom="5%"))
    # member_grid_polar.render(names[member_index]+'clock_grid.html')

    # member_grid.add(member_grid_polar)
    # member_grid.render(names[member_index]+'_member_grid.html')

    pos_top = 5 + 1.5 + 18 * location_count
    pos_bottom = 100 - (5 + 18 - 1.5 + 18 * location_count)
    # print(pos_left, pos_right, pos_top, pos_bottom)
    basic_indices_page_polar.add(chart=member_clock_radar, grid_opts=opts.GridOpts())
    basic_indices_page_polar.add(chart=member_clock_pie, grid_opts=opts.GridOpts())

    # basic_indices_page_polar.render('basic_indices_page_polar.html')

    for bottom_index in ['reposts', 'comments', 'attitudes']:
        func(eval("line_" + bottom_index), names[member_index], df_month.index.tolist(),
             df_month[bottom_index].tolist())

    # basic_indices_page.add(chart=member_grid,grid_opts=opts.GridOpts(pos_left=f"{5+90/member_number*member_index}%",pos_right=f"{5+90/member_number*(member_index+1)}%"))
    # basic_indices_page.render(names[member_index]+'basic_indices.html')

line_reposts.set_global_opts(title_opts=opts.TitleOpts(title='Reposts Trend of All Members', pos_left="12%"),
                             legend_opts=opts.LegendOpts(pos_bottom="bottom"))
line_comments.set_global_opts(title_opts=opts.TitleOpts(title='Comments Trend of All Members', pos_left="45%"),
                              legend_opts=opts.LegendOpts(pos_bottom="bottom"))
line_attitudes.set_global_opts(title_opts=opts.TitleOpts(title='Attitudes Trend of All Members', pos_left="79%"),
                               legend_opts=opts.LegendOpts(pos_bottom="bottom"))
line_reposts.set_series_opts(label_opts=opts.LabelOpts(is_show=False))
line_comments.set_series_opts(label_opts=opts.LabelOpts(is_show=False))
line_attitudes.set_series_opts(label_opts=opts.LabelOpts(is_show=False))
basic_indices_page_bottom.add(chart=line_reposts, grid_opts=opts.GridOpts(pos_left="5%", pos_right="69%"))
basic_indices_page_bottom.add(chart=line_comments, grid_opts=opts.GridOpts(pos_left="38%", pos_right="36%"))
basic_indices_page_bottom.add(chart=line_attitudes, grid_opts=opts.GridOpts(pos_left="71%", pos_right="2%"))
# basic_indices_page_bottom.render('basic_indices_page_bottom.html')
basic_indices_blank_line_legend = (Line(init_opts=opts.InitOpts(width=f'{800 * member_number}px', height='30px'))
                                   .add_yaxis("reposts", [])
                                   .add_yaxis("comments", [])
                                   .add_yaxis("attitudes", [])
                                   .set_global_opts(
    legend_opts=opts.LegendOpts(is_show=True, pos_left='center', pos_top="0%")))
basic_indices_blank_bar_legend = (Bar(init_opts=opts.InitOpts(width=f'{800 * member_number}px', height='30px'))
                                  .add_yaxis("too few samples in the time period", [],
                                             itemstyle_opts=opts.ItemStyleOpts(opacity=0.2))
                                  .add_yaxis("numbers", [], itemstyle_opts=opts.ItemStyleOpts(opacity=0.8))
                                  .set_global_opts(
    legend_opts=opts.LegendOpts(is_show=True, pos_left='center', pos_bottom="0%")))
basic_indices_blank_legend = (Grid(init_opts=opts.InitOpts(width=f'{800 * member_number}px', height='50px'))
                              .add(chart=basic_indices_blank_line_legend, grid_opts=opts.GridOpts(pos_top="100px"))
                              .add(chart=basic_indices_blank_bar_legend, grid_opts=opts.GridOpts(pos_top="100px")))
basic_indices_page.add(basic_indices_page_vertical)
basic_indices_page.add(basic_indices_page_polar)
basic_indices_page.add(basic_indices_blank_legend)
basic_indices_page.add(basic_indices_page_bottom)
basic_indices_page.render('basic_indices.html')