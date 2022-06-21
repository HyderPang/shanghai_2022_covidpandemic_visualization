import numpy as np
import requests
import re
import pandas as pd
from bs4 import BeautifulSoup
import lxml
from tqdm import notebook
import os

import plotly.graph_objects as go
import plotly.express as px
import plotly.offline as pltoff
import plotly.figure_factory as ff


def read_first_line(descriptions):
    regstr = '\d+年\d+月\d+日'
    regexp_date = re.compile(regstr)
    regstr = '，(.*)区'
    regexp_district = re.compile(regstr)
    regstr = '\d+例本土(.*)确诊'
    regexp_confirmedCases = re.compile(regstr)
    regstr = '\d+例(|新冠肺炎)(|本土)无症状'
    regexp_asymptomaticCases = re.compile(regstr)

    districtname = re.search(regexp_district, descriptions)
    if districtname:
        districtname = districtname[0]
        if '，' in districtname:
            districtname = districtname.split('，')[1]

    date = re.search(regexp_date, descriptions)[0]

    confirmed = re.search(regexp_confirmedCases, descriptions)
    if confirmed:
        confirmed = int(re.search('\d+', confirmed[0])[0])
    else:
        confirmed = None

    asymptomatic = re.search(regexp_asymptomaticCases, descriptions)
    if asymptomatic:
        asymptomatic = int(re.search('\d+', asymptomatic[0])[0])
    else:
        asymptomatic = None

    return districtname, date, confirmed, asymptomatic


def get_metadata(url, minimal_address_size=3):
    html = requests.get(url)
    soup = BeautifulSoup(html.text, 'lxml')

    regstr = u'，|。|、|；'
    regexp_address = re.compile(regstr, re.IGNORECASE)
    regstr = u'分别居住于'
    regexp_firstline = re.compile(regstr, re.IGNORECASE)
    shanghai = soup.find_all('span', text=regexp_firstline)

    addresses = {}
    confirmedCases = {}
    asymptomaticCases = {}

    for district in shanghai:
        district = district.parent.parent

        # Line-one
        descriptions = district.parent.parent.p.get_text()
        districtname, date, confirmed, asymptomatic = read_first_line(descriptions)
        # print(districtname, date, confirmed, asymptomatic)

        # find address
        flag = False
        address_list = []
        for address in district.children:
            address = address.get_text()
            if not address:
                if not flag:
                    flag = True
                else:
                    flag = False
                    break
            if flag:
                address = re.split(regexp_address, address)
                if len(address) > 1 and len(address[0]) > minimal_address_size:
                    address = address[0]
                    address_list.append(address)

        addresses[districtname] = address_list
        confirmedCases[districtname] = confirmed
        asymptomaticCases[districtname] = asymptomatic
    return date, addresses, confirmedCases, asymptomaticCases


def get_gd_loc(address,
               key='c13c96adfa738532fcef1b2ecb931f77',
               url='https://restapi.amap.com/v3/geocode/geo?parameters',
               city='上海',
               timeout=5):
    if not address:
        return None, None

    address_ = ''
    batch = 'false'
    num_batch = 1
    address_validmask = []
    if isinstance(address, list):
        batch = 'true'
        num_batch = len(address)
        for add in address:
            if add:
                address_validmask.append(True)
            else:
                address_validmask.append(False)
            address_ += add + ' | '
        address = address_[:-1]

    parameters = {'address': address, 'key': key, 'city': city, 'batch': batch}

    requests.packages.urllib3.disable_warnings()
    try:
        response = requests.get(url, parameters, timeout=2, verify=False)
        assert response.status_code == 200
        answer = response.json()
        assert answer['status'] == '1'
    except Exception as e:
        print(e)
        raise

    loc = []
    for batch_id in range(num_batch):
        loc.append(answer['geocodes'][batch_id]['location'])
    return loc, answer


def get_csv(url):
    date, addresses, confirmedCases, asymptomaticCases = get_metadata(url)
    date_l = []
    district_l = []
    address_l = []
    lats = []
    lons = []

    date_dec = re.findall('\d+', date)
    date_dec = np.datetime64('%4d-%02d-%02d' % (int(date_dec[0]),
                                                int(date_dec[1]), int(date_dec[2])))
    for district in addresses.keys():
        for i_add in addresses[district]:
            date_l.append(date_dec)
            district_l.append(district)
            address_l.append(i_add)

    batch_size = 10
    for i in notebook.tqdm(range(0, len(address_l), batch_size), desc=url):
        add = address_l[i:i + batch_size]
        locs, answer = get_gd_loc(add)
        for loc in locs:
            if isinstance(loc, list):
                lons.append(None)
                lats.append(None)
            else:
                loc = loc.split(',')
                lons.append(float(loc[0]))
                lats.append(float(loc[1]))

    df_dict = {"date": date_l, "district": district_l, "address": address_l,
               "lons": lons, "lats": lats}
    df = pd.DataFrame(df_dict)
    filename = 'shanghai/' + date + '.csv'
    if filename in os.listdir():
        os.remove(filename)
    df.to_csv(filename, encoding='utf_8_sig', index=None)


if __name__ == '__main__':
    urls = ['https://mp.weixin.qq.com/s/8bljTUplPh1q4MXb6wd_gg',
            'https://mp.weixin.qq.com/s/HTM47mUp0GF-tWXkPeZJlg',
            'https://mp.weixin.qq.com/s/79NsKhMHbg09Y0xaybTXjA',
            'https://mp.weixin.qq.com/s/_Je5_5_HqBcs5chvH5SFfA',
            'https://mp.weixin.qq.com/s/u0XfHF8dgfEp8vGjRtcwXA',
            'https://mp.weixin.qq.com/s/vxFiV2HeSvByINUlTmFKZA',
            'https://mp.weixin.qq.com/s/OZGM-pNkefZqWr0IFRJj1g',
            'https://mp.weixin.qq.com/s/L9AffT-SoEBV4puBa_mRqg',
            'https://mp.weixin.qq.com/s/5T76lht3s6g_KTiIx3XAYw',
            'https://mp.weixin.qq.com/s/ZkhimhWpa92I2EWn3hmd8w',
            'https://mp.weixin.qq.com/s/dRa-PExJr1qkRis88eGCnQ',
            'https://mp.weixin.qq.com/s/LguiUZj-zxy4xy19WO0_UA',
            'https://mp.weixin.qq.com/s/GWI6LxYLHOvv1dioN5olxg',
            'https://mp.weixin.qq.com/s/puNUP9bjYlZNELsse09Z0w',
            'https://mp.weixin.qq.com/s/8qCvsE578Ehz6UcWYRBfXw',
            'https://mp.weixin.qq.com/s/qFvUyEB-R-GKP7vgKR-c3A',
            'https://mp.weixin.qq.com/s/LySBR0VJswl_ZI1KtWlXqw',
            'https://mp.weixin.qq.com/s/YNeLEO7BZouZRfyD2TWOlA',
            'https://mp.weixin.qq.com/s/9-DRQF8pbz_2uivgscOmbw',
            'https://mp.weixin.qq.com/s/IrtFkZDWaB6io18QXwuQ9g',
            'https://mp.weixin.qq.com/s/SIuDbITNdgWwYyM3eiyrgg',
            'https://mp.weixin.qq.com/s/SKkU2W-Ic1H_qWnYC9NtXA',
            'https://mp.weixin.qq.com/s/aDU54MGe9XPWEMrdKMRFww',
            'https://mp.weixin.qq.com/s/aQMZ8WmeYEaBPFv0yVs4BQ',
            'https://mp.weixin.qq.com/s/qbB7VjEXMTK0zB6JIqBbAA',
            'https://mp.weixin.qq.com/s/agdZHOqVZh9atNHOQEFTog',
            'https://mp.weixin.qq.com/s/s_spcc0OApRItbuq5DG2LA',
            'https://mp.weixin.qq.com/s/KyTRqsRBWbM5cEa2sk2wbg',
            'https://mp.weixin.qq.com/s/J68hA0ncRR_q91ccVINP0g',
            'https://mp.weixin.qq.com/s/IqIqMik_fGpPgfNgIZ8ieg',
            'https://mp.weixin.qq.com/s/bqZp2AqqE-FPzJpx6FlhPA',
            'https://mp.weixin.qq.com/s/Dt_Q7mwgzJIdn7NwqeGNeA',
            'https://mp.weixin.qq.com/s/SU8bV1IqoaH2NeUs_HJBzg',
            'https://mp.weixin.qq.com/s/iUhgNb9-2Ofhsg9zxi2hiw',
            'https://mp.weixin.qq.com/s/V9gNghk8vWinad_VT_YAtg',
            'https://mp.weixin.qq.com/s/i4BwsY-a9zXjkJe-FTea4Q',
            'https://mp.weixin.qq.com/s/YyhqHoMgyetDu6kP9-Ybpw',
            'https://mp.weixin.qq.com/s/lIMFiBlzIXvju2VV_I4j0g',
            'https://mp.weixin.qq.com/s/d1qIhfwsisM2jQpfURml3A', ]

    # for url in urls:
    #    get_csv(url)
    get_statistics(urls)

def get_gd_add(locs,
               key='c13c96adfa738532fcef1b2ecb931f77',
               url='https://restapi.amap.com/v3/geocode/regeo?parameters'
               ):
    if isinstance(locs, list) and len(loc)==0:
        return None, None

    loc_ = ''
    batch = 'false'
    num_batch = 1
    loc_validmask = []
    if isinstance(locs, list) or isinstance(locs, np.ndarray):
        batch = 'true'
        num_batch = len(locs)
        for loc in locs:
            if loc.any():
                loc_validmask.append(True)
            else:
                loc_validmask.append(False)
            loc_ += '%.5f,%.5f'%(loc[0], loc[1]) + '|'
        loc_ = loc_[:-1]

    parameters = {'location': loc_, 'key': key, 'batch': batch}
    requests.packages.urllib3.disable_warnings()
    try:
        response = requests.get(url, parameters, timeout=2, verify=False)
        assert response.status_code == 200
        answer = response.json()
        assert answer['status'] == '1'
    except Exception as e:
        print(e)
        raise

    district = []
    township = []
    neighborhood = []
    building = []
    streetNumber = []
    for batch_id in range(num_batch):
        district.append(answer['regeocodes'][batch_id]['addressComponent']['district'])
        township.append(answer['regeocodes'][batch_id]['addressComponent']['township'])
        neighborhood.append(answer['regeocodes'][batch_id]['addressComponent']['neighborhood']['name'])
        building.append(answer['regeocodes'][batch_id]['addressComponent']['building']['name'])
        streetNumber.append(answer['regeocodes'][batch_id]['addressComponent']['streetNumber']['street'])
    return district, township, neighborhood, building, streetNumber


def get_row_from_dfm(dfm, idx, name='asymptomaticCases'):
    date = dfm['date'][0]
    sub_df = dfm.drop('date', axis=1)
    districts = list(sub_df.keys())
    val = list(sub_df.loc[idx])

    new = {'district': districts, name: val}
    new = pd.DataFrame(new)
    return new


def Fig_TollByDistricts(df, json_path='data/shanghai_boundary.jspn'):
    token = open(".mapbox_token").read()
    with open(json_path, encoding='utf-8-sig') as f:
        shanghai_geo = json.load(f)
    color_list = ['#2e598f', '#9abdae', '#d3d179', '#e7c034', ]

    for key in df.keys():
        if key != 'date':
            val_key = key
    fig = go.Figure(go.Choroplethmapbox(geojson=shanghai_geo,
                                        featureidkey='properties.name',
                                        locations=df['district'],
                                        z=df[val_key],
                                        zauto=True,
                                        hovertext=df['district'],
                                        hoverinfo='text + z',
                                        colorscale=color_list
                                        ))

    fig.update_layout(mapbox={'accesstoken': token, 'center': {'lon': 121.47, 'lat': 31.23}, 'zoom': 7.5},
                      title={'text': '上海新冠肺炎' + val_key + '汇总',
                             'xref': 'paper', 'x': 0.5})
    fig.show()


def Fig_Scatter(df, savename=None, time_line=None):
    color_list = ['#1e1e2a', '#293e5d', '#2e598f', '#397ab2', '#59a3c4',
                  '#738a83', '#9abdae', '#e5e8b3', '#d3d179', '#e7c034', ]
    px.set_mapbox_access_token(open(".mapbox_token").read())
    hoverD = {'address': True, 'date': True, 'district': True}
    city_center = {'lon': np.mean(df['lons']), 'lat': np.mean(df['lats'])}

    animation_frame = None
    color = 'date'
    if time_line:
        animation_frame = 'date'
        color = 'district'
    fig = px.scatter_mapbox(df, lat="lats", lon="lons",
                            hover_name="address", hover_data=hoverD,
                            title='上海疫情报告点报告',
                            center=city_center,
                            zoom=8,
                            color=color,
                            color_discrete_sequence=color_list,
                            animation_frame=animation_frame
                            )
    if savename:
        pltoff.plot(fig, filename=savename + '.html')
    fig.show()


def Fig_Heatmap(df, savename=None):
    # Graw Fig
    color_list = [ '#293e5d','#2e598f',  '#9abdae', '#d3d179', '#e7c034', ]

    hovertemplate = '报告病例数: %{z}<br>地址: %{customdata}<extra></extra>'
    streetNumber = []
    for i in range(len(df)):
        streetNumber.append(df['streetNumber'][i])
    token = open(".mapbox_token").read()
    fig = go.Figure(go.Densitymapbox(lon=df['lon'],
                                     lat=df['lat'],
                                     z=df['centroids_dense'],
                                     radius=40,
                                     customdata=df,
                                     hovertemplate=hovertemplate,
                                     colorscale=color_list,
                                     zmin=1,
                                     zmax=3000
                                     ))

    fig.update_layout(mapbox={'accesstoken': token, 'center':{'lon': 121.47, 'lat': 31.23}, 'zoom': 7.5},
                     title={'text': '上海新冠肺炎疫情点热力图',
                            'xref': 'paper', 'x':0.5})
    if savename:
        pltoff.plot(fig, filename=savename+'.html')
    fig.show()

