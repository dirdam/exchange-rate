import streamlit as st
import pandas as pd
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from webdriver_manager.firefox import GeckoDriverManager
import plotly.express as px

st.set_page_config(
    page_title="換算レートの計算",
    page_icon="💱"
    )

st.markdown('# 出張に伴う換算レートの計算')
st.markdown('東京三菱UFJ公表レートより抽出（ http://www.murc-kawasesouba.jp/fx/past_3month.php ）。')
st.markdown('※ 祝日等は前日レートで補完。')

# Fix dates range
st.markdown('#### ① 出張期間を選択してください')
cols = st.columns(2)
first_date = None
with cols[0]:
    first_date = st.date_input('出張開始日', None, max_value=datetime.now())
with cols[1]:
    last_date = st.date_input('出張終了日', None, min_value=first_date, max_value=datetime.now(), disabled=not first_date)
if not first_date or not last_date or first_date > last_date:
    st.stop()

if 'first_date' in st.session_state and st.session_state['first_date'] == first_date and st.session_state['last_date'] == last_date:
    st.session_state['calculate'] = False
    df = st.session_state['df']
else:
    st.session_state['calculate'] = True
    st.session_state['first_date'] = first_date
    st.session_state['last_date'] = last_date

def add_data(df, browser, date):
    # Get TTS and TTB through xpath
    tts = float(browser.find_element(By.XPATH, '/html/body/div[2]/div/table[1]/tbody/tr[2]/td[4]').text)
    ttb = float(browser.find_element(By.XPATH, '/html/body/div[2]/div/table[1]/tbody/tr[2]/td[5]').text)
    # Add data to dataframe
    df.loc[len(df)] = [date, tts, ttb, (tts + ttb) / 2]
    return df

if st.session_state['calculate']: # Calculate only if dates have changed
    # Get all dates between first_date and last_date
    dates = pd.date_range(start=first_date, end=last_date, freq='D')
    # Sort dates in ascending order
    dates = dates.sort_values()

    # Initialize dataframe
    df = pd.DataFrame(columns=['日付', 'TTS', 'TTB', '(TTS+TTB)/2'])
    # Function to add data to dataframe
    def add_data(df, browser, date):
        # Get TTS and TTB through xpath
        tts = float(browser.find_element(By.XPATH, '//*[@id="main"]/table[1]/tbody/tr[2]/td[4]').text)
        ttb = float(browser.find_element(By.XPATH, '//*[@id="main"]/table[1]/tbody/tr[2]/td[5]').text)
        # Add data to dataframe
        df.loc[len(df)] = [date.strftime('%y-%m-%d'), tts, ttb, (tts + ttb) / 2]
        return df

    # Open browser
    options = Options()
    options.add_argument('--headless')
    service = Service(GeckoDriverManager().install())
    browser = webdriver.Firefox(service=service, options=options)
    base_url = 'https://www.murc-kawasesouba.jp/fx/past/index.php?id='
    # Loop through dates
    progress_text = 'データ取得中...'
    my_bar = st.progress(0, text=progress_text) # Initialize progress bar
    for i, date in enumerate(dates):
        my_bar.progress((i+1)/len(dates), text=progress_text) # Update progress bar
        url = base_url + date.strftime('%y%m%d')
        browser.get(url)
        if browser.current_url == url: # If date has valid data (not weekend or holiday)
            df = add_data(df, browser, date)
        else:
            try: # If not first date, add previous date data
                df.loc[len(df)] = [date.strftime('%y-%m-%d'), df['TTS'].iloc[-1], df['TTB'].iloc[-1], df['(TTS+TTB)/2'].iloc[-1]]
            except: # Go back day by day until we find a valid date
                temp_date = date
                while True:
                    temp_date -= pd.Timedelta(days=1)
                    url = base_url + temp_date.strftime('%y%m%d')
                    browser.get(url)
                    if browser.current_url == url:
                        df = add_data(df, browser, date)
                        break
            continue
    browser.quit()
    my_bar.empty() # Clear progress bar

    with st.expander('換算レートの値の詳細を見る'):
        st.write(df)

    # Save dataframe to session state
    st.session_state['df'] = df

# Median
median = df['(TTS+TTB)/2'].median()
# Sum
sum = df['(TTS+TTB)/2'].sum()

# Show graph
st.markdown(f'#### ② 為替')#中央値 = <span style="color:blue;">{median:.2f}¥/$</span>', unsafe_allow_html=True)
st.markdown('出張期間中の換算レートを表示します。')
fig = px.line(df.dropna(), x='日付', y='(TTS+TTB)/2', title='換算レートの推移')
fig.add_hline(y=median, line_dash='dash', line_color='red', annotation_text=f'中央値：{median:.2f}', annotation_position='bottom right')
st.plotly_chart(fig)

# Add 日当 and multiply by median
st.markdown('#### ③ 日当計算')
st.markdown('日々の換算レートの値を基に、日当を計算します。')
per_diem = st.number_input('一日当たりの日当（ドル建て）を入力してください', min_value=0, max_value=1000, value=45, step=1)
st.markdown(f"""計算値：
- 出張期間中の**ピッタリ**の該当日当（円建て）：**{sum*per_diem:,.2f} 円** ({len(df)}日間分)
- **中央値**を基準にした場合の該当日当（円建て）： **{median*len(df)*per_diem:,.2f} 円** [ = {per_diem}ドル × {len(df)}日 × {median}円/ドル/日]
- **帰国日の換算レート**を基準にした場合の該当日当（円建て）： **{df['(TTS+TTB)/2'].iloc[-1]*len(df)*per_diem:,.2f} 円** [ {per_diem}ドル × {len(df)}日 × {df['(TTS+TTB)/2'].iloc[-1]}円/ドル/日]""")